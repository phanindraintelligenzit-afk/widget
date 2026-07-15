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
    return build_sub_metrics(obs, settings, s)


def enrich_productivity_sub_metrics(s: Session, sub_metrics: dict) -> dict:
    if "P" not in sub_metrics:
        sub_metrics["P"] = {}

    p_eval_map = {}
    if s is not None:
        p_evals = repo.list_latest_productivity_resource_evaluations(s)
        if p_evals:
            p_eval_map = {f"{r.resource_name}:{r.metric}": r.current_value for r in p_evals}

    completed_tasks = sub_metrics["P"].get("completed") or 1
    
    def safe_float(val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
            
    t_d = safe_float(p_eval_map.get("Apache SkyWalking:token_depth"))
    a_c = safe_float(p_eval_map.get("Grafana Tempo:api_calls"))
    d_b = safe_float(p_eval_map.get("OpenTelemetry:decision_branches"))
    
    alpha1, alpha2, alpha3 = 0.001, 2.5, 5.0
    N_AI = completed_tasks
    
    e_c_ai = ((alpha1 * t_d) + (alpha2 * a_c) + (alpha3 * d_b)) / max(N_AI, 1)
    e_c_human = safe_float(p_eval_map.get("OpenTelemetry:human_complexity"), 10.0)
    
    gamma = e_c_ai / max(e_c_human, 0.0001) if e_c_ai > 0 else 1.0
    effective_output = completed_tasks * gamma
    
    # Do not overwrite human_baseline with e_c_human. Retain existing or 0.0.
    h_base = sub_metrics["P"].get("human_baseline") or 0.0
    
    sub_metrics["P"].update({
        "E[C_AI]": e_c_ai,
        "E[C_Human]": e_c_human,
        "gamma": gamma,
        "effective_output": effective_output,
        "token_depth": t_d,
        "api_calls": a_c,
        "decision_branches": d_b,
        "worker_concurrency": safe_float(p_eval_map.get("OpenTelemetry:worker_concurrency"), 1.0),
        "execution_duration": safe_float(p_eval_map.get("Grafana Tempo:execution_duration"), 0.0),
        "throughput": safe_float(p_eval_map.get("Apache SkyWalking:throughput"), 0.0),
        "resolution_velocity": safe_float(p_eval_map.get("Grafana Tempo:resolution_velocity"), 0.0),
        "human_baseline": h_base,
        "normalization_factor": gamma,
    })
    return sub_metrics

def enrich_quality_sub_metrics(s: Session, sub_metrics: dict) -> dict:
    if "Q" not in sub_metrics:
        return sub_metrics

    q_eval_map = {}
    if s is not None:
        q_evals = repo.list_latest_quality_resource_evaluations(s)
        if q_evals:
            q_eval_map = {f"{r.resource_name}:{r.metric}": r.current_value for r in q_evals}

    accuracy_str = sub_metrics["Q"].get("QA Accuracy") or q_eval_map.get("Ragas:semantic_accuracy", "Unavailable")
    consistency_str = sub_metrics["Q"].get("Consistency") or q_eval_map.get("AgentOps:consistency_measurement", "Unavailable")
    hallucination_str = sub_metrics["Q"].get("Hallucination Rate") or q_eval_map.get("LangSmith:hallucination_analysis", "Unavailable")
    
    try:
        if "Unavailable" not in (accuracy_str, consistency_str, hallucination_str) and "" not in (accuracy_str, consistency_str, hallucination_str):
            acc = float(accuracy_str)
            cons = float(consistency_str)
            hall = float(hallucination_str)
            q_score = (0.7 * acc) + (0.2 * cons) + (0.1 * (1.0 - hall))
            q_score = round(q_score, 4)
            status = "COMPLETED"
        else:
            q_score = sub_metrics["Q"].get("Quality Score") if sub_metrics["Q"].get("Quality Score") != "Pending SME Review" else None
            status = sub_metrics["Q"].get("Status", "Pending SME Review")
    except (ValueError, TypeError):
        q_score = None
        status = sub_metrics["Q"].get("Status", "Pending SME Review")

    if "Groundedness" in sub_metrics["Q"]:
        del sub_metrics["Q"]["Groundedness"]

    sub_metrics["Q"].update({
        "QA Accuracy": accuracy_str,
        "Hallucination Rate": hallucination_str,
        "Consistency": consistency_str,
        "Quality Score": q_score if q_score is not None else "Pending SME Review",
        "Status": status,
        "runtime_traces": q_eval_map.get("LangSmith:runtime_traces") or sub_metrics["Q"].get("runtime_traces", "Unavailable"),
        "llm_evaluation": q_eval_map.get("LangSmith:llm_evaluation") or sub_metrics["Q"].get("llm_evaluation", "Unavailable"),
        "hallucination_analysis": hallucination_str,
        "prompt_evaluation": q_eval_map.get("LangSmith:prompt_evaluation") or sub_metrics["Q"].get("prompt_evaluation", "Unavailable"),
        "context_evaluation": q_eval_map.get("LangSmith:context_evaluation") or sub_metrics["Q"].get("context_evaluation", "Unavailable"),
        "semantic_accuracy": accuracy_str,
        "faithfulness": q_eval_map.get("Ragas:faithfulness") or sub_metrics["Q"].get("faithfulness", "Unavailable"),
        "answer_relevancy": q_eval_map.get("Ragas:answer_relevancy") or sub_metrics["Q"].get("answer_relevancy", "Unavailable"),
        "context_precision": q_eval_map.get("Ragas:context_precision") or sub_metrics["Q"].get("context_precision", "Unavailable"),
        "context_recall": q_eval_map.get("Ragas:context_recall") or sub_metrics["Q"].get("context_recall", "Unavailable"),
        "runtime_execution_history": q_eval_map.get("AgentOps:runtime_execution_history") or sub_metrics["Q"].get("runtime_execution_history", "Unavailable"),
        "agent_behaviour": q_eval_map.get("AgentOps:agent_behaviour") or sub_metrics["Q"].get("agent_behaviour", "Unavailable"),
        "consistency_measurement": consistency_str,
        "session_metrics": q_eval_map.get("AgentOps:session_metrics") or sub_metrics["Q"].get("session_metrics", "Unavailable"),
        "stability_metrics": q_eval_map.get("AgentOps:stability_metrics") or sub_metrics["Q"].get("stability_metrics", "Unavailable"),
    })
    return sub_metrics

def enrich_execution_sub_metrics(s: Session, sub_metrics: dict) -> dict:
    if "E" not in sub_metrics:
        return sub_metrics

    e_eval_map = {}
    if s is not None:
        e_evals = repo.list_latest_execution_resource_evaluations(s)
        if e_evals:
            e_eval_map = {f"{r.resource_name}:{r.metric}": r.current_value for r in e_evals}

    # Inject metrics tracked by Execution resources (Langfuse, Phoenix, Traceloop)
    sub_metrics["E"].update({
        "trace_captured": e_eval_map.get("Langfuse:trace_captured") or sub_metrics["E"].get("trace_captured", "Unavailable"),
        "trace_id": e_eval_map.get("Langfuse:trace_id") or sub_metrics["E"].get("trace_id", "Unavailable"),
        "trace_status": e_eval_map.get("Langfuse:trace_status") or sub_metrics["E"].get("trace_status", "Unavailable"),
        "execution_success": e_eval_map.get("Langfuse:execution_success") or sub_metrics["E"].get("execution_success", "Unavailable"),
        "workflow_execution": e_eval_map.get("Traceloop:workflow_execution") or sub_metrics["E"].get("workflow_execution", "Unavailable"),
        "workflow_status": e_eval_map.get("Traceloop:workflow_status") or sub_metrics["E"].get("workflow_status", "Unavailable"),
        "root_span": e_eval_map.get("Traceloop:root_span") or sub_metrics["E"].get("root_span", "Unavailable"),
        "iterations_used": e_eval_map.get("Phoenix:iterations_used") or sub_metrics["E"].get("iterations_used", "Unavailable"),
        "successful_executions": e_eval_map.get("Phoenix:successful_executions") or sub_metrics["E"].get("successful_executions", "Unavailable"),
        "execution_status": e_eval_map.get("Phoenix:execution_status") or sub_metrics["E"].get("execution_status", "Unavailable"),
    })
    return sub_metrics

def build_sub_metrics(obs: AgentObservation, settings, s: Session = None) -> dict[str, Any]:
    res: dict[str, Any] = {}
    prod = obs.productivity if getattr(obs, "productivity", None) else getattr(obs, "tasks", None)
    if prod:
        res["P"] = prod.model_dump(mode="json")
        res = enrich_productivity_sub_metrics(s, res)
        from contract.models import Productivity
        if not getattr(obs, "productivity", None):
            obs.productivity = Productivity()
        obs.productivity.normalization_factor = res["P"].get("normalization_factor", 1.0)
        obs.productivity.human_baseline = res["P"].get("human_baseline", 10.0)
        obs.productivity.effective_output = res["P"].get("effective_output", 0.0)
    if obs.quality:
        q_raw = obs.quality.model_dump(mode="json")
        res["Q"] = {
            "QA Accuracy": q_raw.get("accuracy"),
            "Consistency": q_raw.get("consistency"),
            "Hallucination Rate": q_raw.get("hallucination_rate"),
            "User Feedback": q_raw.get("user_feedback_score", "N/A") if q_raw.get("user_feedback_score") is not None else "N/A"
        }
        res = enrich_quality_sub_metrics(s, res)
        
        # Update obs.quality so scoring uses the enriched values
        q_score = res["Q"].get("Quality Score")
        if q_score != "Pending SME Review" and q_score is not None:
            try:
                obs.quality.accuracy = float(res["Q"].get("QA Accuracy", 0))
                obs.quality.consistency = float(res["Q"].get("Consistency", 0))
                obs.quality.hallucination_rate = float(res["Q"].get("Hallucination Rate", 0))
            except (ValueError, TypeError):
                pass
    if obs.executions:
        res["E"] = obs.executions.model_dump(mode="json")
        res = enrich_execution_sub_metrics(s, res)
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

        req = 0
        val = 0
        eval_map = {}
        if s is not None:
            evals = repo.list_latest_validation_resource_evaluations(s)
            eval_map = {f"{r.resource_name}:{r.metric}": r.current_value for r in evals}
            for r in evals:
                if not r.metric.endswith("_evidence"):
                    req += 1
                    if r.status == "SUCCESS":
                        val += 1
        
        # Fallback to static if no runtime evaluations exist (e.g., tests without bootstrap)
        if req == 0:
            req = v_raw.get("required_components") or 6
            val = v_raw.get("validated_components") or 0

        v_score = (val / max(req, 1)) * 100

        res["V"] = {
            "Required Components": req,
            "Validated Components": val,
            "Validation Score": v_score,
            
            # DeepEval
            "answer_relevancy": eval_map.get("DeepEval:answer_relevancy") or (f"{obs.quality.accuracy:.3f}" if obs.quality else "Unavailable"),
            "faithfulness": eval_map.get("DeepEval:faithfulness") or (f"{obs.quality.consistency:.3f}" if obs.quality else "Unavailable"),
            "hallucination": eval_map.get("DeepEval:hallucination") or (f"{obs.quality.hallucination_rate:.3f}" if obs.quality else "Unavailable"),
            # correctness: distinct fallback — use consistency (not accuracy, to avoid dup with answer_relevancy)
            "correctness": eval_map.get("DeepEval:correctness") or (f"{obs.quality.consistency:.3f}" if obs.quality else "Unavailable"),
            "evaluation_status": eval_map.get("DeepEval:evaluation_status") or ("COMPLETED" if obs.quality else "Unavailable"),
            "evaluation_count": eval_map.get("DeepEval:evaluation_count") or "Unavailable",

            # Jaeger
            "trace_id": eval_map.get("Jaeger:trace_id") or "Unavailable",
            "runtime_trace_count": eval_map.get("Jaeger:validation_traces") or "Unavailable",
            "span_count": eval_map.get("Jaeger:span_count") or "Unavailable",
            "latency": eval_map.get("Jaeger:latency") or "Unavailable",
            "execution_time": eval_map.get("Jaeger:execution_time") or "Unavailable",
            "dependency_graph": eval_map.get("Jaeger:dependencies") or "Unavailable",
            "request_duration": eval_map.get("Jaeger:request_duration") or "Unavailable",
            "error_count": eval_map.get("Jaeger:error_count") or "Unavailable",

            # Zipkin
            "trace_timeline": eval_map.get("Zipkin:trace_timeline") or "Unavailable",
            "span_timeline": eval_map.get("Zipkin:span_timeline") or "Unavailable",
            "service_calls": eval_map.get("Zipkin:service_calls") or "Unavailable",
            "request_path": eval_map.get("Zipkin:request_path") or "Unavailable",
            "trace_latency": eval_map.get("Zipkin:trace_latency") or "Unavailable",
            "execution_timeline": eval_map.get("Zipkin:execution_timeline") or "Unavailable",
            "error_timeline": eval_map.get("Zipkin:error_timeline") or "Unavailable",
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




