"""Orchestration: observation -> metrics -> Rating -> persist.

The API layer's only job between request and DB. The engine stays pure
and only sees normalized metrics; this module is where settings + DB
meet the engine.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from contract import AgentBaseline, AgentObservation, PartialObservation, Rating, merge_partials, Incident
from engine import metrics_from_observation, metrics_from_partial, rate
from store import repo

# Define Gauges matching the required DPI-LS metric names
# All gauges are defined and managed inside api/metrics_exporter.py to avoid duplicates.

def update_prometheus_metrics(agent_id: str, rating: Rating) -> None:
    pass


def _sync_metrics_from_sub_metrics(
    metrics: dict[str, Optional[float]],
    sub_metrics: dict,
) -> None:
    """Override metrics[G] and metrics[R] from live sub_metrics values.

    Guarantees that the same normalized number feeds both:
    - rating.weighted_metrics (via composite() → drives the agent row),
    - rating.sub_metrics.{G,R}.* (drives the detail panel).

    Only overrides when live evidence exists in the DB — a fresh install
    with no seeded governance evaluations or risk incidents will fall
    back to the observation-derived values, so unit tests that don't
    seed the DB continue to pass unchanged.
    """
    g_sub = sub_metrics.get("G") or {}
    # Only override metrics[G] when the observation itself already
    # provided a G value (i.e. this agent's obs.policy was populated)
    # AND live telemetry exists in the DB. A partial observation that
    # never emitted G stays None. The override uses the official
    # formula output (0–1 space) computed from runtime telemetry:
    #   G = 1 - (Total Actions / Policy Violations)
    if (
        metrics.get("G") is not None
        and "Formula Output" in g_sub
        and ((g_sub.get("Total Actions") or 0) > 0 or (g_sub.get("Policy Violations") or 0) > 0)
    ):
        try:
            metrics["G"] = float(g_sub["Formula Output"])
        except (TypeError, ValueError):
            pass

    r_sub = sub_metrics.get("R") or {}
    # Same policy for R — only override when the observation gave us
    # a value AND there is at least one active incident. A partial
    # observation without incidents leaves R as None.
    if (
        metrics.get("R") is not None
        and (r_sub.get("Total Active Incidents") or 0) > 0
        and "Risk Score" in r_sub
    ):
        try:
            metrics["R"] = float(r_sub["Risk Score"])
        except (TypeError, ValueError):
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
    
    # Load Risk Incidents
    from sqlalchemy import select
    from store.models import RiskIncidentRow
    
    incidents_db = s.scalars(
        select(RiskIncidentRow).where(RiskIncidentRow.agent_id == obs.agent_id)
    ).all()
    
    obs.incidents = [
        Incident(
            id=inc.incident_id,
            name=inc.name,
            source=inc.source_resource,
            category=inc.category,
            severity=inc.severity,
            frequency=inc.frequency,
            severity_weight=inc.severity_weight,
            contribution=inc.risk_contribution
        )
        for inc in incidents_db
    ]
    
    metrics = metrics_from_observation(obs, settings, baseline_obj)

    # Single source of truth: build sub_metrics first, then sync live
    # G/R values back into `metrics` so that rating.weighted_metrics
    # (row) and rating.sub_metrics (detail panel) can never drift.
    #
    # The observation payload has an initial G/R read; the DB has
    # authoritative live values from GovernanceResourceEvaluationRow
    # and RiskIncidentRow. When live data exists we prefer it — the
    # dashboard's "20.00 vs 13.89" bug was caused by these two paths
    # producing different values.
    sub_metrics = _extract_sub_metrics(obs, settings, baseline_obj, s)
    _sync_metrics_from_sub_metrics(metrics, sub_metrics)

    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )
    # Surface RAG signals (informational — doesn't affect score math).
    rating.retrievals = obs.retrievals
    rating.retrieved_docs_total = obs.retrieved_docs_total
    rating.sub_metrics = sub_metrics
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
    sub_metrics = _extract_sub_metrics(merged, settings, baseline, s)
    _sync_metrics_from_sub_metrics(metrics, sub_metrics)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )
    rating.sub_metrics = sub_metrics

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
            
        from store.models import EnterpriseProductivityResourceEvaluationRow
        from sqlalchemy import select
        ep_evals = s.scalars(select(EnterpriseProductivityResourceEvaluationRow)).all()
        if ep_evals:
            p_eval_map.update({f"{r.resource_name}:{r.metric}": r.current_value for r in ep_evals})

    completed_tasks = sub_metrics["P"].get("completed") or 1
    
    def safe_float(val, default=0.0):
        try:
            if val is not None:
                return float(val)
        except (ValueError, TypeError):
            pass
        try:
            if default is not None:
                return float(default)
        except (ValueError, TypeError):
            pass
        return 0.0
            
    # Extract complexity metrics from Langfuse & Prometheus
    t_d = safe_float(p_eval_map.get("Langfuse:token_usage"), p_eval_map.get("Apache SkyWalking:token_depth"))
    a_c = safe_float(p_eval_map.get("Langfuse:prompt_executions"), p_eval_map.get("Grafana Tempo:api_calls"))
    d_b = safe_float(p_eval_map.get("Prometheus:queue_length"), p_eval_map.get("OpenTelemetry:decision_branches"))
    
    alpha1, alpha2, alpha3 = 0.001, 2.5, 5.0
    N_AI = completed_tasks
    
    e_c_ai = ((alpha1 * t_d) + (alpha2 * a_c) + (alpha3 * d_b)) / max(N_AI, 1)
    e_c_human = safe_float(p_eval_map.get("Prometheus:human_complexity"), 10.0)
    
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
        "worker_concurrency": safe_float(p_eval_map.get("Prometheus:concurrency"), 1.0),
        "execution_duration": safe_float(p_eval_map.get("Langfuse:execution_duration"), 0.0),
        "throughput": safe_float(p_eval_map.get("Langfuse:task_throughput"), 0.0),
        "cpu_usage": safe_float(p_eval_map.get("Prometheus:cpu"), 0.0),
        "memory_usage": safe_float(p_eval_map.get("Prometheus:memory"), 0.0),
        "infrastructure_health": p_eval_map.get("Prometheus:infrastructure_health", "Healthy"),
        "success_rate": safe_float(p_eval_map.get("Langfuse:success_rate"), 100.0),
        "failure_rate": safe_float(p_eval_map.get("Langfuse:failure_rate"), 0.0),
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

        from store.models import EnterpriseQualityResourceEvaluationRow
        from sqlalchemy import select
        eq_evals = s.scalars(select(EnterpriseQualityResourceEvaluationRow)).all()
        if eq_evals:
            q_eval_map.update({f"{r.resource_name}:{r.metric}": r.current_value for r in eq_evals})

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
        "Consistency": consistency_str,
        "Hallucination Rate": hallucination_str,
        "Quality Score": q_score,
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
    
    # DeepEval, TruLens, Confident AI injected into Q
    sub_metrics["Q"].update({
        "answer_relevancy": q_eval_map.get("Confident AI:answer_relevancy") or q_eval_map.get("DeepEval:Answer Relevancy") or sub_metrics["Q"].get("answer_relevancy", "Unavailable"),
        "faithfulness": q_eval_map.get("Confident AI:faithfulness") or q_eval_map.get("DeepEval:Faithfulness") or sub_metrics["Q"].get("faithfulness", "Unavailable"),
        "hallucination": q_eval_map.get("Confident AI:hallucination") or q_eval_map.get("DeepEval:Hallucination Score") or sub_metrics["Q"].get("hallucination", "Unavailable"),
        "correctness": q_eval_map.get("Confident AI:correctness") or q_eval_map.get("DeepEval:Correctness") or sub_metrics["Q"].get("correctness", "Unavailable"),
        "ground_truth_accuracy": q_eval_map.get("TruLens:ground_truth_accuracy") or sub_metrics["Q"].get("ground_truth_accuracy", "Unavailable"),
        "trulens_faithfulness": q_eval_map.get("TruLens:trulens_faithfulness") or sub_metrics["Q"].get("trulens_faithfulness", "Unavailable"),
        "hallucination_detection": q_eval_map.get("TruLens:hallucination_detection") or sub_metrics["Q"].get("hallucination_detection", "Unavailable"),
    })
    return sub_metrics

def enrich_validation_sub_metrics(s: Session, sub_metrics: dict) -> dict:
    if "V" not in sub_metrics:
        return sub_metrics

    v_eval_map = {}
    if s is not None:
        v_evals = repo.list_latest_validation_resource_evaluations(s)
        if v_evals:
            v_eval_map = {f"{r.resource_name}:{r.metric}": r.current_value for r in v_evals}
            
        from store.models import EnterpriseValidationResourceEvaluationRow, EnterpriseQualityResourceEvaluationRow
        from sqlalchemy import select
        ev_evals = s.scalars(select(EnterpriseValidationResourceEvaluationRow)).all()
        if ev_evals:
            v_eval_map.update({f"{r.resource_name}:{r.metric}": r.current_value for r in ev_evals})
            
        eq_evals = s.scalars(select(EnterpriseQualityResourceEvaluationRow)).all()
        if eq_evals:
            v_eval_map.update({f"{r.resource_name}:{r.metric}": r.current_value for r in eq_evals})

    sub_metrics["V"].update({
        "trace_id": v_eval_map.get("Jaeger:trace_id") or sub_metrics["V"].get("trace_id", "Unavailable"),
        "validation_traces": v_eval_map.get("Jaeger:validation_traces") or sub_metrics["V"].get("validation_traces", "Unavailable"),
        "span_count": v_eval_map.get("Jaeger:span_count") or sub_metrics["V"].get("span_count", "Unavailable"),
        "latency": v_eval_map.get("Jaeger:latency") or sub_metrics["V"].get("latency", "Unavailable"),
        "execution_time": v_eval_map.get("Jaeger:execution_time") or sub_metrics["V"].get("execution_time", "Unavailable"),
        "dependencies": v_eval_map.get("Jaeger:dependencies") or sub_metrics["V"].get("dependencies", "Unavailable"),
        "request_duration": v_eval_map.get("Jaeger:request_duration") or sub_metrics["V"].get("request_duration", "Unavailable"),
        "error_count": v_eval_map.get("Jaeger:error_count") or sub_metrics["V"].get("error_count", "Unavailable"),
        
        "trace_timeline": v_eval_map.get("Zipkin:trace_timeline") or sub_metrics["V"].get("trace_timeline", "Unavailable"),
        "span_timeline": v_eval_map.get("Zipkin:span_timeline") or sub_metrics["V"].get("span_timeline", "Unavailable"),
        "service_calls": v_eval_map.get("Zipkin:service_calls") or sub_metrics["V"].get("service_calls", "Unavailable"),
        "request_path": v_eval_map.get("Zipkin:request_path") or sub_metrics["V"].get("request_path", "Unavailable"),
        "trace_latency": v_eval_map.get("Zipkin:trace_latency") or sub_metrics["V"].get("trace_latency", "Unavailable"),
        "execution_timeline": v_eval_map.get("Zipkin:execution_timeline") or sub_metrics["V"].get("execution_timeline", "Unavailable"),
        "error_timeline": v_eval_map.get("Zipkin:error_timeline") or sub_metrics["V"].get("error_timeline", "Unavailable"),
        
        # DeepEval in Validation (as expected by JS)
        "answer_relevancy": v_eval_map.get("DeepEval:Answer Relevancy") or sub_metrics["V"].get("answer_relevancy", "Unavailable"),
        "faithfulness": v_eval_map.get("DeepEval:Faithfulness") or sub_metrics["V"].get("faithfulness", "Unavailable"),
        "hallucination": v_eval_map.get("DeepEval:Hallucination Score") or sub_metrics["V"].get("hallucination", "Unavailable"),
        "correctness": v_eval_map.get("DeepEval:Correctness") or sub_metrics["V"].get("correctness", "Unavailable"),
        "evaluation_status": v_eval_map.get("DeepEval:Evaluation Status") or sub_metrics["V"].get("evaluation_status", "Unavailable"),
        "evaluation_count": v_eval_map.get("DeepEval:Evaluation Count") or sub_metrics["V"].get("evaluation_count", "Unavailable"),

        "structural_validation": v_eval_map.get("Guardrails AI:structural_validation") or sub_metrics["V"].get("structural_validation", "Unavailable"),
        "schema_enforcement": v_eval_map.get("Guardrails AI:schema_enforcement") or sub_metrics["V"].get("schema_enforcement", "Unavailable"),
        "guardrails_passed": v_eval_map.get("Guardrails AI:guardrails_passed") or sub_metrics["V"].get("guardrails_passed", "Unavailable"),
        "guardrails_failed": v_eval_map.get("Guardrails AI:guardrails_failed") or sub_metrics["V"].get("guardrails_failed", "Unavailable"),
        
        "type_safe_parsing": v_eval_map.get("Pydantic AI:type_safe_parsing") or sub_metrics["V"].get("type_safe_parsing", "Unavailable"),
        "validation_errors": v_eval_map.get("Pydantic AI:validation_errors") or sub_metrics["V"].get("validation_errors", "Unavailable"),
        "schema_validation": v_eval_map.get("Pydantic AI:schema_validation") or sub_metrics["V"].get("schema_validation", "Unavailable"),
        
        "structured_output_validation": v_eval_map.get("Instructor:structured_output_validation") or sub_metrics["V"].get("structured_output_validation", "Unavailable"),
        "schema_mapping": v_eval_map.get("Instructor:schema_mapping") or sub_metrics["V"].get("schema_mapping", "Unavailable"),
        "instructor_passed": v_eval_map.get("Instructor:instructor_passed") or sub_metrics["V"].get("instructor_passed", "Unavailable"),
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

def enrich_risk_sub_metrics(s: Session, sub_metrics: dict, settings=None) -> dict:
    if "R" not in sub_metrics:
        sub_metrics["R"] = {}
        
    incidents = []
    if s is not None:
        from store.repo import list_latest_risk_incidents
        inc_rows = list_latest_risk_incidents(s)
        for row in inc_rows:
            freq = row.frequency or 1
            weight = row.severity_weight or 1.0
            contribution = float(freq) * float(weight)
            incidents.append({
                "name": row.name,
                "category": row.category,
                "source": row.source_resource,
                "severity": row.severity,
                "severity_weight": weight,
                "frequency": freq,
                "contribution": contribution,
                "trace_id": getattr(row, "trace_id", "N/A") or "N/A",
                "span_id": getattr(row, "span_id", "N/A") or "N/A",
                "correlation_id": getattr(row, "correlation_id", "N/A") or "N/A",
                "timestamp": getattr(row, "timestamp", None).isoformat() if getattr(row, "timestamp", None) else "N/A",
            })
            
    total_risk = sum(i["contribution"] for i in incidents)
    r_max = settings.r_max if hasattr(settings, "r_max") else 50.0
    risk_score = max(0.0, 1.0 - (total_risk / r_max))

    total_freq = sum(i["frequency"] for i in incidents)
    avg_severity = sum(i["severity_weight"] for i in incidents) / len(incidents) if incidents else 0.0

    llmguard = {"Prompt Injection Attempts": 0, "Unsafe Prompts": 0, "Blocked Prompts": 0, "Jailbreaks": 0, "Sanitized Prompts": 0}
    rebuff = {"Attack Count": 0, "Injection Attempts": 0, "Blocked Requests": 0, "Allowed Requests": 0, "Injection Confidence": 0}
    trulens = {"Hallucinations": 0, "Groundedness": 0, "Toxicity": 0, "Safety Score": 0, "Feedback Score": 0}

    for inc in incidents:
        # Mock increment counters based on source/category for demonstration 
        src = inc["source"]
        cat = inc["category"]
        if src == "LLMGuard":
            if "Injection" in inc["name"]: llmguard["Prompt Injection Attempts"] += inc["frequency"]
            elif "Unsafe" in inc["name"]: llmguard["Unsafe Prompts"] += inc["frequency"]
            elif "Jailbreak" in inc["name"]: llmguard["Jailbreaks"] += inc["frequency"]
            else: llmguard["Blocked Prompts"] += inc["frequency"]
        elif src == "Rebuff":
            if "Injection" in inc["name"]: rebuff["Injection Attempts"] += inc["frequency"]
            elif "Attack" in inc["name"]: rebuff["Attack Count"] += inc["frequency"]
            else: rebuff["Blocked Requests"] += inc["frequency"]
        elif src == "TruLens":
            if "Hallucination" in inc["name"]: trulens["Hallucinations"] += inc["frequency"]
            elif "Toxic" in inc["name"]: trulens["Toxicity"] += inc["frequency"]
            else: trulens["Safety Score"] += inc["frequency"]

    sub_metrics["R"].update({
        "incidents": incidents,
        "Total Risk": total_risk,
        "Rmax": r_max,
        "Risk Score": risk_score,
        "Total Frequency": total_freq,
        "Average Severity": avg_severity,
        "Aggregated Risk": total_risk,
        "Normalized Risk": total_risk / r_max,
        "Formula Output": risk_score,
        "Critical Incidents": sum(1 for i in incidents if i.get("severity_weight", 0) >= 10.0 or i.get("severity") == "CRITICAL"),
        "Total Active Incidents": len(incidents),
        "Resolved Incidents": 0,
        "Open Incidents": len(incidents),
        "high_incidents": sum(1 for i in incidents if 5.0 <= i.get("severity_weight", 0) < 10.0 or i.get("severity") == "HIGH"),
        "medium_incidents": sum(1 for i in incidents if 2.0 <= i.get("severity_weight", 0) < 5.0 or i.get("severity") == "MEDIUM"),
        "low_incidents": sum(1 for i in incidents if i.get("severity_weight", 0) < 2.0 or i.get("severity") == "LOW"),
        "runtime_resources": {
            "LLMGuard": llmguard,
            "Rebuff": rebuff,
            "TruLens": trulens
        }
    })
    return sub_metrics


def enrich_validation_sub_metrics(s, sub_metrics: dict) -> dict:
    if "V" not in sub_metrics:
        sub_metrics["V"] = {}
        
    if s is not None:
        from store.models import ValidationResourceEvaluationRow
        from sqlalchemy import select
        evals = s.scalars(select(ValidationResourceEvaluationRow)).all()
        for r in evals:
            if r.resource_name in ("Guardrails AI", "Pydantic AI", "Instructor"):
                if r.current_value is not None and r.current_value != "Unavailable":
                    sub_metrics["V"][r.metric] = r.current_value
    return sub_metrics

def enrich_cost_sub_metrics(s, sub_metrics: dict) -> dict:
    if "C" not in sub_metrics:
        sub_metrics["C"] = {}
        
    if s is not None:
        from store.models import CostResourceEvaluationRow
        from sqlalchemy import select
        evals = s.scalars(select(CostResourceEvaluationRow)).all()
        for r in evals:
            if r.resource_name in ("OpenLIT", "OpenCost"):
                if r.current_value is not None and r.current_value != "Unavailable":
                    key = f"{r.resource_name}:{r.metric}"
                    sub_metrics["C"][key] = r.current_value
    return sub_metrics


def enrich_governance_sub_metrics(s, sub_metrics: dict) -> dict:
    if "G" not in sub_metrics:
        sub_metrics["G"] = {}

    incidents = []
    if s is not None:
        from sqlalchemy import select
        from store.models import GovernanceIncidentRow
        inc_rows = s.scalars(select(GovernanceIncidentRow).order_by(GovernanceIncidentRow.timestamp.desc())).all()
        for row in inc_rows:
            freq = row.frequency or 1
            weight = row.severity_weight or 1.0
            contribution = float(freq) * float(weight)
            incidents.append({
                "name": row.name,
                "category": row.category,
                "action_name": getattr(row, "action_name", None) or row.category,
                "source": row.source_resource,
                "severity": row.severity,
                "severity_weight": weight,
                "frequency": freq,
                "contribution": contribution,
                "trace_id": getattr(row, "trace_id", "N/A") or "N/A",
                "span_id": getattr(row, "span_id", "N/A") or "N/A",
                "correlation_id": getattr(row, "correlation_id", "N/A") or "N/A",
                "timestamp": getattr(row, "timestamp", None).isoformat() if getattr(row, "timestamp", None) else "N/A",
            })

    opa = {"Policies Executed": 0, "Policies Passed": 0, "Policies Failed": 0, "Denied Requests": 0, "Allowed Requests": 0}
    presidio = {"PII Entities Detected": 0, "Masked Entities": 0, "Mask Failure": 0}
    secrets = {"Secrets Found": 0, "Secrets Blocked": 0, "Critical Secrets": 0, "Files Scanned": 0, "Repositories Scanned": 0}

    if s is not None:
        from store.models import GovernanceResourceEvaluationRow
        from sqlalchemy import select
        evals = s.scalars(select(GovernanceResourceEvaluationRow)).all()
        for r in evals:
            # Populate metrics for dashboard from runtime telemetry only.
            if r.resource_name == "Open Policy Agent":
                if r.metric in opa and r.current_value is not None:
                    try:
                        opa[r.metric] = int(r.current_value)
                    except (TypeError, ValueError):
                        pass
            elif r.resource_name == "Microsoft Presidio":
                if r.metric in presidio and r.current_value is not None:
                    try:
                        presidio[r.metric] = int(r.current_value)
                    except (TypeError, ValueError):
                        pass
            elif r.resource_name == "Detect-Secrets":
                if r.metric in secrets and r.current_value is not None:
                    try:
                        secrets[r.metric] = int(r.current_value)
                    except (TypeError, ValueError):
                        pass

    for inc in incidents:
        src = inc["source"]
        if src == "Open Policy Agent":
            opa["Policies Failed"] += inc["frequency"]
            opa["Denied Requests"] += inc["frequency"]
        elif src == "Microsoft Presidio":
            presidio["PII Entities Detected"] += inc["frequency"]
            presidio["Mask Failure"] += inc["frequency"]
        elif src == "Detect-Secrets":
            secrets["Secrets Found"] += inc["frequency"]

    # --- Official DPI-LS governance formula, from runtime telemetry only ---
    # Total Actions = sum of real policy-gated actions executed across the
    # three governance telemetry sources (no hardcoded denominators).
    total_actions = (
        (opa.get("Policies Executed") or 0)
        + (presidio.get("PII Entities Detected") or 0)
        + (secrets.get("Secrets Found") or 0)
        + (secrets.get("Files Scanned") or 0)
    )
    # Policy Violations = total observed governance incident frequency.
    policy_violations = sum(inc["frequency"] for inc in incidents)

    if policy_violations <= 0:
        g_formula_output = 1.0
    else:
        g_formula_output = max(0.0, 1.0 - (total_actions / policy_violations))

    sub_metrics["G"].update({
        "incidents": incidents,
        "Total Actions": total_actions,
        "Policy Violations": policy_violations,
        "Formula": "G = 1 - (Policy Violations / Total Actions)",
        "Formula Output": g_formula_output,
        "Total Active Incidents": len(incidents),
        "runtime_resources": {
            "Open Policy Agent": opa,
            "Microsoft Presidio": presidio,
            "Detect-Secrets": secrets
        }
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
    
    # Enrich Risk with incidents from DB
    res = enrich_risk_sub_metrics(s, res, settings)
    res = enrich_governance_sub_metrics(s, res)

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
        }
        res = enrich_validation_sub_metrics(s, res)
    if obs.cost:
        c_raw = obs.cost.model_dump(mode="json")
        in_t = c_raw.get("input_tokens", 0) or 0
        out_t = c_raw.get("output_tokens", 0) or 0
        hc = c_raw.get("Human_cost")
        if hc is None or hc == 0.0:
            hc = settings.human_cost_per_output
        
        pc = in_t * settings.input_token_price
        cc = out_t * settings.output_token_price
        mc = c_raw.get("model_cost", 0.0) or (pc + cc)
        infra_cost = c_raw.get("infrastructure_cost", 0.0) or 0.0
        tco = mc + hc + infra_cost
        
        c_raw["completed_outputs"] = obs.tasks.completed if obs.tasks else 1
        c_raw["input_token_price"] = settings.input_token_price
        c_raw["output_token_price"] = settings.output_token_price
        c_raw["AI Cost Per Output"] = (mc + infra_cost) / max(c_raw["completed_outputs"], 1)
        c_raw["Human Cost / Output"] = hc
        c_raw["Prompt Cost (USD)"] = pc
        c_raw["Completion Cost (USD)"] = cc
        c_raw["Model Cost (USD)"] = mc
        c_raw["Infrastructure Cost (USD)"] = infra_cost
        c_raw["Token Cost (USD)"] = pc + cc
        c_raw["Total Cost (USD)"] = tco
        c_raw["Efficiency Ratio"] = hc / max(c_raw["AI Cost Per Output"], 0.000001)
        c_raw["utilization"] = settings.utilization
        
        # Add dynamic OpenLIT and OpenCost metrics
        if s is not None:
            c_evals = repo.list_latest_cost_resource_evaluations(s)
            for r in c_evals:
                if r.resource_name in ["OpenLIT", "OpenCost"]:
                    if r.status == "SUCCESS" and r.current_value is not None:
                        c_raw[f"{r.resource_name}:{r.metric}"] = r.current_value
        
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




