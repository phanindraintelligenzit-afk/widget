from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from store.db import get_session_factory
from store import repo


def test_standard_metrics_registered_on_bootstrap(client):
    """Verify standard cost metrics are pre-populated by bootstrap."""
    response = client.get("/api/cost/metrics/definitions")
    assert response.status_code == 200
    defs = response.json()
    assert len(defs) >= 23
    
    ids = {d["id"] for d in defs}
    assert "llm_token_cost" in ids
    assert "salary_cost" in ids
    assert "compute_cost" in ids
    assert "total_cost_of_ownership" in ids


def test_register_custom_cost_metric_definition(client):
    """Verify we can register new metric definitions dynamically."""
    payload = {
        "id": "custom_gpu_tax",
        "category": "ai",
        "display_name": "Custom GPU Tax",
        "description": "Additional tax for custom private hosting",
        "source_system": "Internal FinOps",
        "unit": "USD"
    }
    response = client.post("/api/cost/metrics/definitions", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["id"] == "custom_gpu_tax"
    assert res["category"] == "ai"

    # Verify it shows up in definitions list
    defs = client.get("/api/cost/metrics/definitions").json()
    ids = {d["id"] for d in defs}
    assert "custom_gpu_tax" in ids


def test_ingest_cost_value_fails_on_unregistered_metric(client):
    """Verify that posting values to unregistered metrics raises 400."""
    payload = {
        "agent_id": "test-agent-001",
        "metric_id": "non_existent_metric",
        "value": 100.0,
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z"
    }
    response = client.post("/api/cost/values", json=payload)
    assert response.status_code == 400
    assert "not registered" in response.json()["detail"]


def test_dynamic_cost_calculation_flow(client):
    """Test dynamic cost values ingestion, rescoring, and detailed calculation."""
    # 1. Create an agent and trigger initial clean score
    agent_id = "cost-agent-dynamic"
    start_str = "2026-06-01T00:00:00Z"
    end_str = "2026-06-02T00:00:00Z"

    # Initial ingest to bootstrap the agent with 2 completed outputs
    initial_payload = {
        "agent_id": agent_id,
        "agent_name": "Dynamic Cost Agent",
        "period_start": start_str,
        "period_end": end_str,
        "tasks": {"assigned": 2, "completed": 2, "failed": 0},
        "executions": {"attempts": 2, "successful": 2},
        "policy": {"total_actions": 2, "violations": []},
        "validation": {"required_components": 0, "validated_components": 0},
        "cost": {"input_tokens": 0, "output_tokens": 0, "model_cost": 0.0},
        "source": "manual"
    }
    r = client.post("/ingest", json=initial_payload)
    assert r.status_code == 200

    # Clean score should have C=1.0 since model_cost=0.0
    rating = client.get(f"/agents/{agent_id}/score").json()
    assert rating["metrics"]["C"] == 1.0

    # 2. Ingest dynamic cost values
    # Ingest AI metric value
    client.post("/api/cost/values", json={
        "agent_id": agent_id,
        "metric_id": "llm_token_cost",
        "value": 8.0,
        "period_start": start_str,
        "period_end": end_str
    })

    # Ingest System metric value
    client.post("/api/cost/values", json={
        "agent_id": agent_id,
        "metric_id": "compute_cost",
        "value": 2.0,
        "period_start": start_str,
        "period_end": end_str
    })

    # Ingest Human salary metric value (human baseline per period)
    client.post("/api/cost/values", json={
        "agent_id": agent_id,
        "metric_id": "salary_cost",
        "value": 30.0,
        "period_start": start_str,
        "period_end": end_str
    })

    # Ingest dynamic utilization factor
    client.post("/api/cost/values", json={
        "agent_id": agent_id,
        "metric_id": "utilization_factor",
        "value": 0.85,
        "period_start": start_str,
        "period_end": end_str
    })

    # 3. Request calculation summary endpoint
    calc_resp = client.get(
        f"/api/cost/agents/{agent_id}/calculate",
        params={"period_start": start_str, "period_end": end_str, "completed_outputs": 2}
    )
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()

    # Total AI model cost = AI (8.0) + System (2.0) = 10.0
    assert calc_data["model_cost"] == 10.0
    # Total Human cost = 30.0
    assert calc_data["Human_cost"] == 30.0
    # AI cost per output = 10.0 / 2 = 5.0
    assert calc_data["ai_cost_per_output"] == 5.0
    # Human cost per output = 30.0 / 2 = 15.0
    assert calc_data["human_cost_per_output"] == 15.0
    # Ratio = 15.0 / 5.0 = 3.0 (capped at 1.0)
    # Score = 1.0 * 0.85 (utilization) = 0.85
    assert calc_data["utilization"] == 0.85
    assert len(calc_data["audit_trail"]) == 4

    # 4. Verify score history contains the rescored C rating
    rating_after = client.get(f"/agents/{agent_id}/score").json()
    assert rating_after["metrics"]["C"] == pytest.approx(0.85)
