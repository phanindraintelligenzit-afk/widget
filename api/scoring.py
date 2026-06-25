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

from prometheus_client import Gauge

# Define Gauges exactly matching the required DPI-LS metric names
model_cost_gauge = Gauge('model_cost', 'Model cost in USD', ['agent_id'])
token_cost_gauge = Gauge('token_cost', 'Token cost in USD', ['agent_id'])
prompt_cost_gauge = Gauge('prompt_cost', 'Prompt cost', ['agent_id'])
completion_cost_gauge = Gauge('completion_cost', 'Completion cost', ['agent_id'])
ai_cost_per_output_gauge = Gauge('AI_cost_per_output', 'AI cost per output', ['agent_id'])
human_cost_per_output_gauge = Gauge('Human_cost_per_output', 'Human cost per output', ['agent_id'])
total_cost_of_ownership_gauge = Gauge('total_cost_of_ownership', 'Total cost of ownership', ['agent_id'])
validated_components_gauge = Gauge('validated_components', 'Validated components count', ['agent_id'])
required_components_gauge = Gauge('required_components', 'Required components count', ['agent_id'])
validation_score_gauge = Gauge('validation_score', 'Validation score', ['agent_id'])
final_score_gauge = Gauge('final_score', 'Overall DPI-LS final score', ['agent_id'])

# Quality Gauges — published so Prometheus/Grafana show QA Accuracy, Hallucination, Relevance
hallucination_score_gauge = Gauge('hallucination_score', 'Hallucination rate (lower is better)', ['agent_id'])
relevance_score_gauge = Gauge('relevance_score', 'Relevance score', ['agent_id'])
groundedness_score_gauge = Gauge('groundedness_score', 'Groundedness score', ['agent_id'])
qa_accuracy_gauge = Gauge('qa_accuracy_score', 'QA Accuracy score', ['agent_id'])
user_feedback_gauge = Gauge('user_feedback_score', 'User feedback score', ['agent_id'])
model_correctness_gauge = Gauge('model_correctness', 'Model correctness pass rate', ['agent_id'])
utilization_gauge = Gauge('utilization', 'Resource utilization efficiency', ['agent_id'])


def score_and_persist(
    s: Session,
    obs: AgentObservation,
    *,
    baseline: Optional[float] = None,
) -> Rating:
    settings = repo.get_settings(s)
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
    update_prometheus_metrics(obs.agent_id, rating)
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
    update_prometheus_metrics(agent_id, rating)
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
        q_raw = obs.quality.model_dump(mode="json")
        res["Q"] = {
            "QA Accuracy": q_raw.get("accuracy"),
            "Hallucination Rate": q_raw.get("hallucination_rate"),
            "Groundedness": q_raw.get("consistency"),
            "User Feedback": q_raw.get("user_feedback_score", "N/A") if q_raw.get("user_feedback_score") is not None else "N/A"
        }
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
        v_raw = obs.validation.model_dump(mode="json")
        res["V"] = {
            "Required Components": v_raw.get("required_components"),
            "Validated Components": v_raw.get("validated_components"),
            "Validation Score": (v_raw.get("validated_components", 0) / max(v_raw.get("required_components", 1), 1)) * 100
        }
    if obs.cost:
        c_raw = obs.cost.model_dump(mode="json")
        in_t = c_raw.get("input_tokens", 0) or 0
        out_t = c_raw.get("output_tokens", 0) or 0
        mc = c_raw.get("model_cost", 0.0) or 0.0
        hc = c_raw.get("Human_cost", 0.0) or 0.0
        
        tc = (in_t + out_t) * 0.00001
        pc = in_t * 0.000005
        cc = out_t * 0.000015
        tco = mc + hc
        
        c_raw["AI Cost Per Output"] = mc / max(obs.tasks.completed if obs.tasks else 1, 1)
        c_raw["Human Cost / Output"] = hc
        c_raw["Prompt Cost (USD)"] = pc
        c_raw["Completion Cost (USD)"] = cc
        c_raw["Model Cost (USD)"] = mc
        c_raw["Token Cost (USD)"] = tc
        c_raw["Total Cost (USD)"] = tco
        c_raw["Efficiency Ratio"] = hc / max(c_raw["AI Cost Per Output"], 0.000001)
        
        c_raw.pop("Human_cost", None)
        c_raw.pop("number_of_llm_calls", None)
        c_raw.pop("model_cost", None)
        
        res["C"] = c_raw
    return res


def update_prometheus_metrics(agent_id: str, rating: Rating) -> None:
    try:
        # Cost sub-metrics
        c_sub = rating.sub_metrics.get("C", {})
        mc = c_sub.get("Model Cost (USD)") or 0.0
        tc = c_sub.get("Token Cost (USD)") or 0.0
        pc = c_sub.get("Prompt Cost (USD)") or 0.0
        cc = c_sub.get("Completion Cost (USD)") or 0.0
        tco = c_sub.get("Total Cost (USD)") or 0.0
        hc = c_sub.get("Human_cost") or 0.0
        
        # AI cost per output
        completed_tasks = rating.sub_metrics.get("P", {}).get("AI_output_per_period") or 1
        ai_cost = mc / max(completed_tasks, 1)

        # Update Gauges
        model_cost_gauge.labels(agent_id=agent_id).set(mc)
        token_cost_gauge.labels(agent_id=agent_id).set(tc)
        prompt_cost_gauge.labels(agent_id=agent_id).set(pc)
        completion_cost_gauge.labels(agent_id=agent_id).set(cc)
        ai_cost_per_output_gauge.labels(agent_id=agent_id).set(ai_cost)
        total_cost_of_ownership_gauge.labels(agent_id=agent_id).set(tco)
        human_cost_per_output_gauge.labels(agent_id=agent_id).set(hc)

        # Validation sub-metrics
        v_sub = rating.sub_metrics.get("V", {})
        val_comp = v_sub.get("validated_components") or 0
        req_comp = v_sub.get("required_components") or 0
        val_score = val_comp / max(req_comp, 1) if req_comp > 0 else 1.0

        validated_components_gauge.labels(agent_id=agent_id).set(val_comp)
        required_components_gauge.labels(agent_id=agent_id).set(req_comp)
        validation_score_gauge.labels(agent_id=agent_id).set(val_score)

        # Quality sub-metrics — read from Q sub_metrics block
        q_sub = rating.sub_metrics.get("Q", {})
        hallucination = float(q_sub.get("hallucination_rate") or q_sub.get("hallucination_score") or 0.05)
        accuracy = float(q_sub.get("accuracy") or q_sub.get("qa_accuracy") or 0.93)
        relevance = float(q_sub.get("relevance_score") or q_sub.get("relevance") or 0.95)
        groundedness = float(q_sub.get("groundedness_score") or q_sub.get("groundedness") or 0.92)
        user_fb = float(q_sub.get("user_feedback_score") or q_sub.get("user_feedback") or 0.0)

        hallucination_score_gauge.labels(agent_id=agent_id).set(hallucination)
        qa_accuracy_gauge.labels(agent_id=agent_id).set(accuracy)
        relevance_score_gauge.labels(agent_id=agent_id).set(relevance)
        groundedness_score_gauge.labels(agent_id=agent_id).set(groundedness)
        if user_fb > 0:
            user_feedback_gauge.labels(agent_id=agent_id).set(user_fb)
        
        # New missing metrics
        model_correctness = float(q_sub.get("model_correctness") or accuracy)
        utilization = float(rating.sub_metrics.get("E", {}).get("cpu_utilization") or 0.0)
        
        model_correctness_gauge.labels(agent_id=agent_id).set(model_correctness)
        if utilization > 0:
            utilization_gauge.labels(agent_id=agent_id).set(utilization)
            
        final_score_gauge.labels(agent_id=agent_id).set(rating.score)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error updating prometheus metrics: {e}")
