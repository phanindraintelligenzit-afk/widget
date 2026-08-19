with open('api/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

inject = """
@app.post("/api/governance-evaluation/evaluate")
def evaluate_governance(req: AgentRequest, s: Session = Depends(db_session)) -> dict[str, str]:
    from dpi_ls.governance_resource_evaluation_service import GovernanceResourceEvaluationService
    svc = GovernanceResourceEvaluationService(s)
    svc.evaluate_all(req.agent_id)
    return {"status": "ok"}


@app.get("/api/governance-evaluation/resources")
def governance_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import GovernanceResourceRegistryRow
    rows = s.scalars(select(GovernanceResourceRegistryRow)).all()
    return [{
        "id": r.id,
        "name": r.name,
        "sdk_available": r.sdk_available,
        "api_available": r.api_available,
        "api_key_required": r.api_key_required,
        "integration_implemented": r.integration_implemented,
        "created_at": r.created_at.isoformat()
    } for r in rows]


@app.get("/api/governance-evaluation/urls")
def governance_urls(s: Session = Depends(db_session)) -> dict[str, dict]:
    from store.models import GovernanceResourceRegistryRow
    rows = s.scalars(select(GovernanceResourceRegistryRow)).all()
    out = {}
    import os
    for r in rows:
        if r.name == "Open Policy Agent":
            url = os.environ.get("OPA_URL", "https://www.openpolicyagent.org")
            out[r.name] = {"url": url, "online": True}
        elif r.name == "Microsoft Presidio":
            url = os.environ.get("PRESIDIO_URL", "https://microsoft.github.io/presidio")
            out[r.name] = {"url": url, "online": True}
        elif r.name == "Detect-Secrets":
            url = os.environ.get("DETECT_SECRETS_URL", "https://github.com/Yelp/detect-secrets")
            out[r.name] = {"url": url, "online": True}
        else:
            out[r.name] = {"url": "#", "online": False}
    return out


@app.get("/api/governance-evaluation/results")
def governance_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import GovernanceResourceEvaluationRow
    rows = s.scalars(select(GovernanceResourceEvaluationRow)).all()
    return [{
        "id": r.id,
        "resource_name": r.resource_name,
        "metric": r.metric,
        "detected": r.detected,
        "evidence": r.evidence,
        "current_value": r.current_value,
        "last_run": r.last_run.isoformat(),
        "status": r.status,
        "dashboard_verified": r.dashboard_verified,
        "agent_executed": r.agent_executed
    } for r in rows]


@app.post("/api/governance-evaluation/push")
def push_governance_incident(
    req: dict[str, Any],
    s: Session = Depends(db_session)
) -> dict[str, str]:
    from store.models import GovernanceIncidentRow
    from datetime import datetime
    
    agent_id = req.get("agent_id", "default_agent")
    source = req.get("source_resource", "Unknown")
    name = req.get("name", "Incident")
    
    row = GovernanceIncidentRow(
        incident_id=req.get("incident_id", f"gov_{int(datetime.now().timestamp()*1000)}"),
        name=name,
        category=req.get("category", "Policy"),
        source_resource=source,
        agent_id=agent_id,
        severity=req.get("severity", "medium"),
        severity_weight=float(req.get("severity_weight", 1.0)),
        frequency=int(req.get("frequency", 1)),
        risk_contribution=float(req.get("risk_contribution", 1.0)),
        trace_id=req.get("trace_id"),
        span_id=req.get("span_id"),
        correlation_id=req.get("correlation_id")
    )
    s.add(row)
    s.commit()
    return {"status": "ok", "incident_id": row.incident_id}


@app.get("/api/governance-evaluation/dashboard/{agent_id}")
def governance_dashboard_data(agent_id: str, s: Session = Depends(db_session)) -> dict[str, Any]:
    from store.models import GovernanceIncidentRow, GovernanceResourceEvaluationRow
    
    incidents = s.scalars(
        select(GovernanceIncidentRow).where(GovernanceIncidentRow.agent_id == agent_id)
    ).all()
    
    resource_evals = s.scalars(
        select(GovernanceResourceEvaluationRow)
    ).all()
    
    return {
        "agent_id": agent_id,
        "incidents": [{
            "name": i.name,
            "category": i.category,
            "source": i.source_resource,
            "severity": i.severity,
            "severity_weight": i.severity_weight,
            "frequency": i.frequency,
            "contribution": i.risk_contribution,
            "trace_id": i.trace_id
        } for i in incidents],
        "resource_evaluations": [{
            "resource": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "status": r.status,
            "value": r.current_value
        } for r in resource_evals]
    }
"""

if 'governance-evaluation/evaluate' not in text:
    text += '\n' + inject
    with open('api/app.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Governance routes injected!')
else:
    print('Governance routes already exist.')
