from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.app import app
from store.models import (
    EnterpriseQualityResourceRegistryRow,
    EnterpriseQualityResourceEvaluationRow,
)
from dpi_ls.enterprise_quality_evaluation_service import reset_enterprise_quality_collector


def test_enterprise_quality_endpoints(client):
    reset_enterprise_quality_collector()
    # 1. Trigger bootstrapping via the evaluate endpoint or rely on bootstrap
    client.post("/api/enterprise-quality/evaluate")

    # 2. Check resources
    resp = client.get("/api/enterprise-quality/resources")
    assert resp.status_code == 200
    resources = resp.json()
    assert len(resources) == 2
    names = {r["resource_name"] for r in resources}
    assert "DeepEval" in names
    assert "TruLens" in names

    # 3. Check results before any pushes
    resp = client.get("/api/enterprise-quality/results")
    assert resp.status_code == 200
    results = resp.json()
    # Should have a baseline zeroed out for all supported metrics
    assert len(results) > 10
    deepeval_f1 = next((r for r in results if r["resource_name"] == "DeepEval" and r["metric"] == "F1"), None)
    assert deepeval_f1 is not None
    assert deepeval_f1["current_value"] == "0"
    assert deepeval_f1["agent_executed"] is False

    # 4. Push telemetry
    push_resp = client.post("/api/enterprise-quality/push", json={
        "adapter": "DeepEval",
        "metric_name": "Correctness",
        "score": 0.95,
        "passed": True,
        "expected": "Met thresholds",
        "actual": "Score: 0.95",
        "correlation_id": "test-123"
    })
    assert push_resp.status_code == 200
    assert push_resp.json()["recorded"] is True

    push_resp = client.post("/api/enterprise-quality/push", json={
        "adapter": "TruLens",
        "metric_name": "Hallucination Detection",
        "score": 0.05,
        "passed": True,
    })
    assert push_resp.status_code == 200

    # 5. Check results after push
    resp = client.get("/api/enterprise-quality/results")
    results = resp.json()
    correctness = next(r for r in results if r["resource_name"] == "DeepEval" and r["metric"] == "Correctness")
    assert correctness["current_value"] == "0.95"
    assert correctness["agent_executed"] is True
    assert correctness["status"] == "SUCCESS"

    hallucination = next(r for r in results if r["resource_name"] == "TruLens" and r["metric"] == "Hallucination Detection")
    assert hallucination["current_value"] == "0.05"
    assert hallucination["agent_executed"] is True

    # 6. Check Dashboard
    resp = client.get("/api/enterprise-quality/agent-dashboard")
    assert resp.status_code == 200
    dash = resp.json()
    
    # Formula components:
    # Q = 0.7 * Accuracy + 0.2 * Consistency + 0.1 * (1 - Hallucination Rate)
    # Correctness goes to Accuracy -> 0.95
    # Consistency defaults to 1.0 since Accuracy is present
    # Hallucination Detection goes to Hallucination Rate -> 0.05
    # Q = 0.7 * 0.95 + 0.2 * 1.0 + 0.1 * 0.95 = 0.665 + 0.2 + 0.095 = 0.96
    assert dash["accuracy"] == 0.95
    assert dash["hallucination_rate"] == 0.05
    assert dash["consistency"] == 1.0
    assert dash["quality_score"] == 0.96
    assert dash["band"] == "Excellent"
    assert dash["action"] == "Autonomous Trusted"
    
    match_analysis = dash["match_analysis"]
    assert len(match_analysis) == 2
    
    # 7. Reset for test isolation
    reset_enterprise_quality_collector()
