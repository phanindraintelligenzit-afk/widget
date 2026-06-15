"""Orchestration: observation -> metrics -> Rating -> persist.

The API layer's only job between request and DB. The engine stays pure
and only sees normalized metrics; this module is where settings + DB
meet the engine.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from contract import AgentBaseline, AgentObservation, PartialObservation, Rating, merge_partials
from engine import metrics_from_observation, metrics_from_partial, rate
from store import repo


def score_and_persist(
    s: Session,
    obs: AgentObservation,
    *,
    baseline: Optional[float] = None,
) -> Rating:
    settings = repo.get_settings(s)
    
    # Calculate dynamic validation score
    from dpi_ls.validation_service import ValidationService
    val_summary = ValidationService.evaluate_validation(
        s=s,
        agent_id=obs.agent_id,
        period_start=obs.period_start,
        period_end=obs.period_end,
    )
    if val_summary["required_components"] > 0 or obs.validation is not None:
        if obs.validation is None:
            from contract.models import Validation
            obs.validation = Validation(required_components=0, validated_components=0)
        obs.validation.required_components = val_summary["required_components"]
        obs.validation.validated_components = val_summary["validated_components"]

    # Calculate dynamic cost
    from dpi_ls.cost_service import CostService
    completed = obs.tasks.completed if obs.tasks else 0
    costs_summary = CostService.calculate_costs(
        s=s,
        agent_id=obs.agent_id,
        period_start=obs.period_start,
        period_end=obs.period_end,
        completed_outputs=completed,
        fallback_human_cost=settings.human_cost_per_output,
        fallback_utilization=settings.utilization,
    )
    if obs.cost is None:
        from contract.models import Cost
        obs.cost = Cost()
    obs.cost.model_cost = costs_summary["model_cost"]
    obs.cost.Human_cost = costs_summary["Human_cost"]
    if costs_summary["input_tokens"] > 0:
        obs.cost.input_tokens = costs_summary["input_tokens"]
    if costs_summary["output_tokens"] > 0:
        obs.cost.output_tokens = costs_summary["output_tokens"]
    if costs_summary["number_of_llm_calls"] > 0:
        obs.cost.number_of_llm_calls = costs_summary["number_of_llm_calls"]
        
    settings.human_cost_per_output = costs_summary["human_cost_per_output"]
    settings.utilization = costs_summary["utilization"]

    agent = repo.upsert_agent(s, obs.agent_id, obs.agent_name, baseline=baseline)
    baseline_obj = AgentBaseline(
        agent_id=obs.agent_id,
        human_output_per_period=agent.baseline_human_output,
    )
    metrics = metrics_from_observation(obs, settings, baseline_obj)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )
    # Surface RAG signals (informational — doesn't affect score math).
    rating.retrievals = obs.retrievals
    rating.retrieved_docs_total = obs.retrieved_docs_total
    rating.sub_metrics = _extract_sub_metrics(obs, settings, baseline_obj)
    obs_row = repo.save_observation(s, obs)
    repo.save_score(s, obs.agent_id, obs_row.id, rating)
    return rating


def rescore_from_partials(s: Session, agent_id: str) -> Rating | None:
    """Re-merge every stored partial for this agent and rate the result.

    Returns None if the agent has no partials. Persists the score linked
    to the most recent partial's id so history stays causal.
    """
    partials = repo.partials_for_agent(s, agent_id)
    if not partials:
        return None

    merged = merge_partials(partials)
    settings = repo.get_settings(s)
    
    # Calculate dynamic validation score
    from dpi_ls.validation_service import ValidationService
    val_summary = ValidationService.evaluate_validation(
        s=s,
        agent_id=merged.agent_id,
        period_start=merged.period_start,
        period_end=merged.period_end,
    )
    if val_summary["required_components"] > 0 or merged.validation is not None:
        if merged.validation is None:
            from contract.models import Validation
            merged.validation = Validation(required_components=0, validated_components=0)
        merged.validation.required_components = val_summary["required_components"]
        merged.validation.validated_components = val_summary["validated_components"]

    # Calculate dynamic cost
    from dpi_ls.cost_service import CostService
    completed = merged.tasks.completed if merged.tasks else 0
    costs_summary = CostService.calculate_costs(
        s=s,
        agent_id=merged.agent_id,
        period_start=merged.period_start,
        period_end=merged.period_end,
        completed_outputs=completed,
        fallback_human_cost=settings.human_cost_per_output,
        fallback_utilization=settings.utilization,
    )
    if merged.cost is None:
        from contract.models import Cost
        merged.cost = Cost()
    merged.cost.model_cost = costs_summary["model_cost"]
    merged.cost.Human_cost = costs_summary["Human_cost"]
    if costs_summary["input_tokens"] > 0:
        merged.cost.input_tokens = costs_summary["input_tokens"]
    if costs_summary["output_tokens"] > 0:
        merged.cost.output_tokens = costs_summary["output_tokens"]
    if costs_summary["number_of_llm_calls"] > 0:
        merged.cost.number_of_llm_calls = costs_summary["number_of_llm_calls"]
        
    settings.human_cost_per_output = costs_summary["human_cost_per_output"]
    settings.utilization = costs_summary["utilization"]

    agent = repo.upsert_agent(s, merged.agent_id, merged.agent_name or merged.agent_id)
    baseline = AgentBaseline(
        agent_id=merged.agent_id,
        human_output_per_period=agent.baseline_human_output,
    )
    metrics = metrics_from_partial(merged, settings, baseline)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )
    rating.sub_metrics = _extract_sub_metrics(merged, settings, baseline)

    # Link the score to the most recent partial — gives history a sensible
    # causal anchor even though the score is from the merged set.
    from store.models import PartialObservationRow
    from sqlalchemy import select
    most_recent_id = s.scalar(
        select(PartialObservationRow.id)
        .where(PartialObservationRow.agent_id == agent_id)
        .order_by(PartialObservationRow.received_at.desc(), PartialObservationRow.id.desc())
        .limit(1)
    )
    if most_recent_id is not None:
        repo.save_score(s, agent_id, most_recent_id, rating)
    else:
        # Race condition or empty table — skip persisting this score to avoid
        # a NULL FK violation on Postgres. The rating is still returned so the
        # caller gets the right answer; it will be re-persisted on the next ingest.
        import logging
        logging.getLogger(__name__).warning(
            "rescore_from_partials: no partial row found for agent '%s'; "
            "score not persisted.", agent_id,
        )
    return rating


def ingest_partials(s: Session, partials: list[PartialObservation]) -> list[Rating]:
    """Persist each partial, then re-score every distinct agent touched."""
    affected: set[str] = set()
    for p in partials:
        repo.upsert_agent(s, p.agent_id, p.agent_name or p.agent_id)
        repo.save_partial(s, p)
        affected.add(p.agent_id)
    out: list[Rating] = []
    for agent_id in sorted(affected):
        r = rescore_from_partials(s, agent_id)
        if r is not None:
            out.append(r)
    return out


def _extract_sub_metrics(obs: AgentObservation | PartialObservation, settings, baseline) -> dict:
    """Extract raw components from the observation for UI drill-downs.

    The per-agent card renders each dimension's sub-metrics under a
    click-to-expand panel. The C panel in particular benefits from
    the breakdown ``input_tokens`` / ``output_tokens`` / ``model_cost``
    rather than a single rolled-up ``tokens`` figure — the user can
    see at a glance whether the spend is prompt-heavy (large input)
    or completion-heavy (large output).
    """
    res: dict = {}
    if obs.tasks:
        res["P"] = {
            "AI_output_per_period": obs.tasks.completed,
            "human_baseline": baseline.human_output_per_period,
            "normalization_factor": settings.normalization_factor
        }
    if obs.quality:
        res["Q"] = obs.quality.model_dump(mode="json")
    if obs.executions:
        res["E"] = obs.executions.model_dump(mode="json")
    if obs.policy:
        res["G"] = obs.policy.model_dump(mode="json")
    if obs.incidents is not None:
        # Incident carries a numeric ``severity_weight`` (0..1) rather
        # than a string label — bucket it for the UI summary. Cutoffs
        # match the R sub-metric story (R formula treats >= 0.7 as
        # severe contribution to Σ(freq × severity)).
        high = sum(1 for i in obs.incidents if float(i.severity_weight) >= 0.7)
        med  = sum(1 for i in obs.incidents if 0.3 <= float(i.severity_weight) < 0.7)
        low  = sum(1 for i in obs.incidents if float(i.severity_weight) < 0.3)
        res["R"] = {"high_incidents": high, "medium_incidents": med, "low_incidents": low}
    if obs.validation:
        res["V"] = obs.validation.model_dump(mode="json")
    if obs.cost:
        # ``model_dump`` already emits the new breakdown fields
        # (input_tokens, output_tokens, model_cost) in addition to
        # the engine input (ai_cost_per_output) and the non-model
        # observability fields (cloud_cost, systems_accessed).
        res["C"] = obs.cost.model_dump(mode="json")
    return res


def rescore_agent(s: Session, agent_id: str) -> Optional[Rating]:
    """Rescore an agent, handling both partial observations and canonical observations."""
    rating = rescore_from_partials(s, agent_id)
    if rating is not None:
        return rating

    # If no partials exist, look for the latest canonical observation
    obs_row = repo.latest_observation(s, agent_id)
    if obs_row is None:
        return None

    # Load canonical observation
    obs = AgentObservation.model_validate(obs_row.payload)
    return score_and_persist(s, obs)
