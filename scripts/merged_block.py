# ---- Additive: parallel API namespace /api/enterprise-productivity/* ----

@app.get("/api/enterprise-productivity/urls")
def enterprise_productivity_urls(s: Session = Depends(db_session)) -> dict[str, dict]:
    from store.models import EnterpriseProductivityResourceRegistryRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseProductivityResourceRegistryRow)).all()
    out: dict[str, dict] = {}
    for r in rows:
        out[r.name] = {
            "url": r.documentation_url or "#",
            "online": True,
            "sdk_available": bool(r.sdk_available),
        }
    return out


@app.get("/api/enterprise-productivity/resources")
def enterprise_productivity_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import EnterpriseProductivityResourceRegistryRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseProductivityResourceRegistryRow)).all()
    return [
        {
            "id": r.id,
            "resource_name": r.name,
            "category": "Productivity",
            "sdk_available": r.sdk_available,
            "documentation_url": r.documentation_url,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.get("/api/enterprise-productivity/results")
def enterprise_productivity_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import EnterpriseProductivityResourceEvaluationRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseProductivityResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
            "last_run": r.last_run.isoformat() if r.last_run else None,
        }
        for r in rows
    ]


@app.post("/api/enterprise-productivity/evaluate")
def enterprise_productivity_evaluate(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.enterprise_productivity_evaluation_service import (
        EnterpriseProductivityEvaluationService,
    )
    from store.models import EnterpriseProductivityResourceEvaluationRow
    from sqlalchemy import select as _select

    EnterpriseProductivityEvaluationService(s).run_evaluations()
    rows = s.scalars(_select(EnterpriseProductivityResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "agent_executed": r.agent_executed,
        }
        for r in rows
    ]


@app.post("/api/enterprise-productivity/push")
def enterprise_productivity_push(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from dpi_ls.enterprise_productivity_evaluation_service import (
        ProductivityEvent,
        get_enterprise_productivity_collector,
        EnterpriseProductivityEvaluationService,
    )
    adapter = payload.get("adapter")
    metric_name = payload.get("metric_name")
    if not adapter or not metric_name:
        raise HTTPException(400, "adapter and metric_name are required")
    event = ProductivityEvent(
        adapter=str(adapter),
        metric_name=str(metric_name),
        value=payload.get("value"),
        expected=payload.get("expected"),
        actual=payload.get("actual"),
        passed=bool(payload.get("passed", False)),
        latency_ms=float(payload.get("latency_ms", 0.0)),
        correlation_id=payload.get("correlation_id"),
    )
    get_enterprise_productivity_collector().record(event)
    EnterpriseProductivityEvaluationService(s).run_evaluations()
    return {"recorded": True, "adapter": adapter, "metric_name": metric_name, "passed": event.passed}


@app.get("/api/enterprise-productivity/agent-dashboard")
def enterprise_productivity_agent_dashboard(
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from dpi_ls.enterprise_productivity_evaluation_service import (
        PRODUCTIVITY_CANONICAL_MAP,
        get_enterprise_productivity_collector,
        ADAPTERS
    )
    collector = get_enterprise_productivity_collector()
    dpi = collector.dpi_ls_metrics()
    canonical = collector.canonical()
    events = collector.events()

    match_rows: list[dict[str, Any]] = []
    for ev in events:
        match_rows.append({
            "adapter": ev.adapter,
            "metric_name": ev.metric_name,
            "expected": _stringify(ev.expected),
            "actual": _stringify(ev.actual),
            "value": ev.value,
            "matched": ev.passed,
            "status": "MATCH" if ev.passed else "MISMATCH",
            "correlation_id": ev.correlation_id,
            "timestamp": ev.timestamp.isoformat(),
        })

    from store import repo
    settings = repo.get_settings(s)
    p_weight = float(settings.weights.get("P", 0.15))
    dpi["weight"] = p_weight
    if dpi.get("productivity_score") is not None:
        dpi["weighted_contribution"] = round(dpi["productivity_score"] * p_weight, 4)

    return {
        **dpi,
        "canonical_metrics": canonical,
        "match_analysis": match_rows,
        "adapters": [
            {
                "name": a.name,
                "sdk_installed": a.sdk_installed(),
                "documentation_url": a.documentation_url,
                "metrics_supported": list(a.metrics_supported),
            }
            for a in ADAPTERS
        ],
    }


# ---- Additive: parallel API namespace /api/enterprise-risk/* ----

@app.get("/api/enterprise-risk/urls")
def enterprise_risk_urls(s: Session = Depends(db_session)) -> dict[str, dict]:
    from store.models import EnterpriseRiskResourceRegistryRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseRiskResourceRegistryRow)).all()
    out: dict[str, dict] = {}
    for r in rows:
        out[r.name] = {
            "url": r.documentation_url or "#",
            "online": True,
            "sdk_available": bool(r.sdk_available),
        }
    return out


@app.get("/api/enterprise-risk/resources")
def enterprise_risk_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import EnterpriseRiskResourceRegistryRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseRiskResourceRegistryRow)).all()
    return [
        {
            "id": r.id,
            "resource_name": r.name,
            "category": "Risk",
            "sdk_available": r.sdk_available,
            "documentation_url": r.documentation_url,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.get("/api/enterprise-risk/results")
def enterprise_risk_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import EnterpriseRiskResourceEvaluationRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseRiskResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
            "last_run": r.last_run.isoformat() if r.last_run else None,
        }
        for r in rows
    ]


@app.post("/api/enterprise-risk/evaluate")
def enterprise_risk_evaluate(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.enterprise_risk_evaluation_service import (
        EnterpriseRiskEvaluationService,
    )
    from store.models import EnterpriseRiskResourceEvaluationRow
    from sqlalchemy import select as _select

    EnterpriseRiskEvaluationService(s).run_evaluations()
    rows = s.scalars(_select(EnterpriseRiskResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "agent_executed": r.agent_executed,
        }
        for r in rows
    ]


@app.post("/api/enterprise-risk/push")
def enterprise_risk_push(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from dpi_ls.enterprise_risk_evaluation_service import (
        RiskEvent,
        get_enterprise_risk_collector,
        EnterpriseRiskEvaluationService,
    )
    adapter = payload.get("adapter")
    kind = payload.get("kind")
    if not adapter or not kind:
        raise HTTPException(400, "adapter and kind are required")
    event = RiskEvent(
        adapter=str(adapter),
        kind=str(kind),
        severity=str(payload.get("severity", "medium")),
        frequency=int(payload.get("frequency", 1)),
        expected=payload.get("expected"),
        actual=payload.get("actual"),
        resolved=bool(payload.get("resolved", False)),
        error_message=payload.get("error_message"),
        correlation_id=payload.get("correlation_id"),
        latency_ms=float(payload.get("latency_ms", 0.0)),
    )
    get_enterprise_risk_collector().record(event)
    EnterpriseRiskEvaluationService(s).run_evaluations()
    return {"recorded": True, "adapter": adapter, "kind": kind, "severity": event.severity}


@app.get("/api/enterprise-risk/agent-dashboard")
def enterprise_risk_agent_dashboard(
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from dpi_ls.enterprise_risk_evaluation_service import (
        RISK_CANONICAL_MAP,
        get_enterprise_risk_collector,
    )
    collector = get_enterprise_risk_collector()
    dpi = collector.dpi_ls_metrics()
    canonical = collector.canonical()
    events = collector.events()

    match_rows: list[dict[str, Any]] = []
    for ev in events:
        match_rows.append({
            "adapter": ev.adapter,
            "kind": ev.kind,
            "severity": ev.severity,
            "frequency": ev.frequency,
            "expected": _stringify(ev.expected),
            "actual": _stringify(ev.actual),
            "matched": ev.resolved,
            "status": "RESOLVED" if ev.resolved else "ACTIVE",
            "correlation_id": ev.correlation_id,
            "timestamp": ev.timestamp.isoformat(),
        })

    settings = repo.get_settings(s)
    r_weight = float(settings.weights.get("R", 0.15))

    return {
        "total_incidents": dpi["total_incidents"],
        "weighted_risk_sum": dpi["weighted_risk_sum"],
        "r_max": dpi["r_max"],
        "risk_score": dpi["risk_score"],
        "weight": r_weight,
        "weighted_contribution": round(dpi["risk_score"] * r_weight, 4),
        "formula": "R = 1 - min(1, Sum(freq x severity) / R_max)",
        "compliance_gate": {
            "threshold": 0.50,
            "current": dpi["risk_score"],
            "triggered": dpi["unsafe"],
            "unsafe": dpi["unsafe"],
            "capped_score": 69 if dpi["unsafe"] else None,
        },
        "canonical_metrics": canonical,
        "match_analysis": match_rows,
        "adapters": [
            {
                "name": a.name,
                "sdk_installed": a.sdk_installed(),
                "documentation_url": a.documentation_url,
                "metrics_supported": list(a.metrics_supported),
            }
            for a in _enterprise_risk_adapters()
        ],
    }


def _enterprise_risk_adapters():
    from dpi_ls.enterprise_risk_evaluation_service import ADAPTERS
    return ADAPTERS


