with open('api/scoring.py', 'r', encoding='utf-8') as f:
    text = f.read()

inject = """
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
    presidio = {"PII Entities Detected": 0, "Masked Entities": 0, "Mask Success": 0, "Mask Failure": 0}
    secrets = {"Secrets Found": 0, "Secrets Blocked": 0, "Critical Secrets": 0, "Files Scanned": 0, "Repositories Scanned": 0}

    req = 0
    val = 0
    if s is not None:
        from store.models import GovernanceResourceEvaluationRow
        from sqlalchemy import select
        evals = s.scalars(select(GovernanceResourceEvaluationRow)).all()
        for r in evals:
            req += 1
            if r.status == "SUCCESS":
                val += 1
            
            # Populate metrics for dashboard
            if r.resource_name == "Open Policy Agent":
                if r.metric in opa and r.current_value:
                    opa[r.metric] = int(r.current_value)
            elif r.resource_name == "Microsoft Presidio":
                if r.metric in presidio and r.current_value:
                    presidio[r.metric] = int(r.current_value)
            elif r.resource_name == "Detect-Secrets":
                if r.metric in secrets and r.current_value:
                    secrets[r.metric] = int(r.current_value)
            
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

    v_score = (val / max(req, 1)) * 100 if req > 0 else 0

    sub_metrics["G"].update({
        "incidents": incidents,
        "Required Controls": req,
        "Validated Controls": val,
        "Validation Score": v_score,
        "Formula Output": v_score,
        "Total Active Incidents": len(incidents),
        "runtime_resources": {
            "Open Policy Agent": opa,
            "Microsoft Presidio": presidio,
            "Detect-Secrets": secrets
        }
    })
    return sub_metrics
"""

if 'enrich_governance_sub_metrics' not in text:
    text = text.replace('def build_sub_metrics(obs: AgentObservation, settings, s: Session = None) -> dict[str, Any]:', inject + '\ndef build_sub_metrics(obs: AgentObservation, settings, s: Session = None) -> dict[str, Any]:')
    text = text.replace('res = enrich_risk_sub_metrics(s, res)', 'res = enrich_risk_sub_metrics(s, res)\n    res = enrich_governance_sub_metrics(s, res)')
    with open('api/scoring.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Governance metrics logic injected into scoring.py!')
else:
    print('Already injected.')

