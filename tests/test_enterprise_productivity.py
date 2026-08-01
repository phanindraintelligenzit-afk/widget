from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.app import app
from store.models import (
    EnterpriseProductivityResourceRegistryRow,
    EnterpriseProductivityResourceEvaluationRow,
)
from dpi_ls.enterprise_productivity_evaluation_service import reset_enterprise_productivity_collector


def test_enterprise_productivity_endpoints(client):
    reset_enterprise_productivity_collector()
    # 1. Trigger bootstrapping via the evaluate endpoint or rely on bootstrap
    client.post("/api/enterprise-productivity/evaluate")

    # 2. Check resources
    resp = client.get("/api/enterprise-productivity/resources")
    assert resp.status_code == 200
    resources = resp.json()
    assert len(resources) == 5
    names = {r["resource_name"] for r in resources}
    assert "Langfuse" in names
    assert "Prometheus" in names

    # 3. Check results before any pushes
    resp = client.get("/api/enterprise-productivity/results")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 10
    langfuse_tasks = next((r for r in results if r["resource_name"] == "Langfuse" and r["metric"] == "Completed Tasks"), None)
    assert langfuse_tasks is not None
    assert langfuse_tasks["current_value"] == "0"
    assert langfuse_tasks["agent_executed"] is False

    # 4. Push telemetry
    push_resp = client.post("/api/enterprise-productivity/push", json={
        "adapter": "Langfuse",
        "metric_name": "Completed Tasks",
        "value": 15.0,
        "passed": True,
        "expected": "10.0 tasks",
        "actual": "15.0 tasks",
        "correlation_id": "test-prod-123"
    })
    assert push_resp.status_code == 200
    assert push_resp.json()["recorded"] is True

    push_resp = client.post("/api/enterprise-productivity/push", json={
        "adapter": "Prometheus",
        "metric_name": "Thread Count",
        "value": 5.0,
        "passed": True,
    })
    assert push_resp.status_code == 200

    # 5. Check results after push
    resp = client.get("/api/enterprise-productivity/results")
    results = resp.json()
    tasks = next(r for r in results if r["resource_name"] == "Langfuse" and r["metric"] == "Completed Tasks")
    assert tasks["current_value"] == "15.0"
    assert tasks["agent_executed"] is True
    assert tasks["status"] == "SUCCESS"

    concurrency = next(r for r in results if r["resource_name"] == "Prometheus" and r["metric"] == "Thread Count")
    assert concurrency["current_value"] == "5.0"
    assert concurrency["agent_executed"] is True

    # 6. Check Dashboard
    resp = client.get("/api/enterprise-productivity/agent-dashboard")
    assert resp.status_code == 200
    dash = resp.json()
    
    # Formula components:
    # P = min(1.0, (AI Tasks * Gamma) / Human Baseline)
    # Tasks = 15.0
    # Gamma = 1.20
    # Human Baseline = 40.0
    # P = min(1.0, (15.0 * 1.20) / 40.0) = min(1.0, 18.0 / 40.0) = min(1.0, 0.45) = 0.45
    assert dash["ai_output"] == 15.0
    assert dash["normalization_factor"] == 1.20
    assert dash["effective_output"] == 18.0
    assert dash["productivity_score"] == 0.45
    assert dash["band"] == "Critical Failure"
    
    match_analysis = dash["match_analysis"]
    assert len(match_analysis) == 2
    
    # 7. Reset for test isolation
    reset_enterprise_productivity_collector()
