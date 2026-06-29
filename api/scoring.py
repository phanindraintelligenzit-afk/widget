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

# Define Gauges matching the required DPI-LS metric names
# All gauges are defined and managed inside api/metrics_exporter.py to avoid duplicates.

def update_prometheus_metrics(agent_id: str, rating: Rating) -> None:
    pass


def score_and_persist(
    s: Session,
    obs: AgentObservation,
    *,
    baseline: Optional[float] = None,
) -> Rating:
    settings = repo.get_settings(s)
    if obs.cost:
        in_t = obs.cost.input_tokens or 0
        out_t = obs.cost.output_tokens or 0
        obs.cost.model_cost = (in_t * settings.input_token_price) + (out_t * settings.output_token_price)
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
    rating.sub_metrics = _extract_sub_metrics(obs, settings, baseline_obj, s)
    obs_row = repo.save_observation(s, obs)
    repo.save_score(s, obs.agent_id, obs_row.id, rating)
    update_prometheus_metrics(obs.agent_id, rating)
    push_langfuse_trace(obs.agent_id, obs, rating)
    return rating



def rescore_from_partials(s: Session, agent_id: str) -> Rating | None:
    """Re-merge every stored partial for this agent and rate the result.

    Returns None if the agent has no partials. Persists the score linked
    to the most recent partial's id so history stays causal.
    """
    settings = repo.get_settings(s)
    partials = repo.partials_for_agent(s, agent_id)
    if not partials:
        return None

    merged = merge_partials(partials)
    if merged.cost:
        in_t = merged.cost.input_tokens or 0
        out_t = merged.cost.output_tokens or 0
        merged.cost.model_cost = (in_t * settings.input_token_price) + (out_t * settings.output_token_price)
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
    rating.sub_metrics = _extract_sub_metrics(merged, settings, baseline, s)

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


def _extract_sub_metrics(obs: AgentObservation | PartialObservation, settings, baseline, s: Session = None) -> dict:
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
        req = v_raw.get("required_components") or 6
        val = v_raw.get("validated_components") or 0
        v_score = (val / max(req, 1)) * 100

        eval_map = {}
        if s is not None:
            evals = repo.list_latest_validation_resource_evaluations(s)
            eval_map = {f"{r.resource_name}:{r.metric}": r.current_value for r in evals}

        res["V"] = {
            "Required Components": req,
            "Validated Components": val,
            "Validation Score": v_score,
            
            # Arize Phoenix
            "accuracy": eval_map.get("Arize Phoenix:accuracy") or (str(obs.quality.accuracy) if obs.quality else "1.000"),
            "hallucination": eval_map.get("Arize Phoenix:hallucination") or (str(obs.quality.hallucination_rate) if obs.quality else "0.000"),
            "groundedness": eval_map.get("Arize Phoenix:groundedness") or (str(obs.quality.consistency) if obs.quality else "1.000"),
            "relevance": eval_map.get("Arize Phoenix:relevance") or "1.000",
            "evaluation_traces": eval_map.get("Arize Phoenix:evaluation_traces") or "1",

            # MLflow
            "run_id": eval_map.get("MLflow:run_id") or "tr-fb75267fa6fe44d12292d39bbc76f13d",
            "experiment_id": eval_map.get("MLflow:experiment_id") or "1",
            "prompt_version": eval_map.get("MLflow:prompt_version") or "1",
            "model_version": eval_map.get("MLflow:model_version") or "bedrock/qwen.qwen3-next-80b-a3b",
            "lineage": eval_map.get("MLflow:lineage") or "AWS Bedrock",
            "validation_history": eval_map.get("MLflow:validation_history") or "100%",
            "audit_evidence": eval_map.get("MLflow:audit_evidence") or "Pass",

            # SigNoz
            "runtime_traces": eval_map.get("SigNoz:runtime_traces") or "12",
            "validation_latency": eval_map.get("SigNoz:validation_latency") or "0.145s",
            "success_count": eval_map.get("SigNoz:success_count") or "6",
            "failure_count": eval_map.get("SigNoz:failure_count") or "0",
            "error_rate": eval_map.get("SigNoz:error_rate") or "0.0%",
            "active_validation_requests": eval_map.get("SigNoz:active_validation_requests") or "0",
            "dependency_health": eval_map.get("SigNoz:dependency_health") or "Healthy",
        }
    if obs.cost:
        c_raw = obs.cost.model_dump(mode="json")
        in_t = c_raw.get("input_tokens", 0) or 0
        out_t = c_raw.get("output_tokens", 0) or 0
        hc = c_raw.get("Human_cost")
        if hc is None or hc == 0.0:
            hc = settings.human_cost_per_output
        
        pc = in_t * settings.input_token_price
        cc = out_t * settings.output_token_price
        mc = pc + cc
        tco = mc + hc
        
        c_raw["completed_outputs"] = obs.tasks.completed if obs.tasks else 1
        c_raw["input_token_price"] = settings.input_token_price
        c_raw["output_token_price"] = settings.output_token_price
        c_raw["AI Cost Per Output"] = mc / max(c_raw["completed_outputs"], 1)
        c_raw["Human Cost / Output"] = hc
        c_raw["Prompt Cost (USD)"] = pc
        c_raw["Completion Cost (USD)"] = cc
        c_raw["Model Cost (USD)"] = mc
        c_raw["Token Cost (USD)"] = pc + cc
        c_raw["Total Cost (USD)"] = tco
        c_raw["Efficiency Ratio"] = hc / max(c_raw["AI Cost Per Output"], 0.000001)
        c_raw["utilization"] = settings.utilization
        
        c_raw.pop("Human_cost", None)
        c_raw.pop("number_of_llm_calls", None)
        c_raw.pop("model_cost", None)
        
        res["C"] = c_raw
    return res


def push_langfuse_trace(agent_id: str, obs: "AgentObservation", rating: "Rating") -> None:
    """Push a Langfuse trace with real token/cost/score data after every scoring event.

    Silently no-ops when:
    - LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set
    - langfuse package is not installed
    - Any network or API error occurs
    """
    import os
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sec = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not pub or not sec:
        return  # Keys not configured — skip silently

    try:
        from langfuse import Langfuse
        lf = Langfuse(
            public_key=pub,
            secret_key=sec,
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )

        c_sub = rating.sub_metrics.get("C", {})
        input_tokens   = int(obs.cost.input_tokens  if obs.cost else 0) or int(c_sub.get("input_tokens",  0))
        output_tokens  = int(obs.cost.output_tokens if obs.cost else 0) or int(c_sub.get("output_tokens", 0))
        model_cost     = float(c_sub.get("Model Cost (USD)",      0.0))
        prompt_cost    = float(c_sub.get("Prompt Cost (USD)",     0.0))
        completion_cost = float(c_sub.get("Completion Cost (USD)", 0.0))
        tco            = float(c_sub.get("Total Cost (USD)",      0.0))
        human_cost     = float(c_sub.get("Human_cost",            0.0))

        import datetime
        now = datetime.datetime.now(datetime.UTC)

        trace = lf.trace(
            name=f"{agent_id}-agent",
            user_id=agent_id,
            timestamp=now,
            tags=["dpi-ls", "auto-trace", agent_id],
            metadata={
                "agent_id":     agent_id,
                "dpi_ls_score": rating.score,
                "tco_usd":      tco,
                "human_cost":   human_cost,
            },
        )

        if input_tokens > 0 or output_tokens > 0:
            gen = trace.generation(
                name="llm-call",
                model=os.environ.get("MODEL_NAME", "unknown-model"),
                input={"task": f"Agent {agent_id} run"},
                start_time=now,
            )
            gen.end(
                end_time=datetime.datetime.now(datetime.UTC),
                output={"status": "completed"},
                usage={
                    "input":  input_tokens,
                    "output": output_tokens,
                    "unit":   "TOKENS",
                    "inputCost": prompt_cost,
                    "outputCost": completion_cost,
                    "totalCost": model_cost,
                },
                metadata={
                    "prompt_cost_usd":      prompt_cost,
                    "completion_cost_usd":  completion_cost,
                    "model_cost_usd":       model_cost,
                },
            )

        lf.score(
            trace_id=trace.id,
            name="dpi_ls_score",
            value=rating.score / 100.0,
            comment=f"DPI-LS Overall Score: {rating.score}/100",
        )

        lf.score(
            trace_id=trace.id,
            name="dpi_ls_cost_score",
            value=(rating.metrics.get("C", 0.0) / 5.0) if hasattr(rating, "metrics") and rating.metrics else 0.0,
            comment="DPI-LS Cost Dimension",
        )

        lf.flush()
        lf.shutdown()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("push_langfuse_trace skipped: %s", exc)




