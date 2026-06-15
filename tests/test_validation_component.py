from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from store.db import get_session_factory
from store import repo


def test_standard_validation_metrics_registered_on_bootstrap(client):
    """Verify standard validation metrics are pre-populated by bootstrap."""
    response = client.get("/api/validation/metrics")
    assert response.status_code == 200
    defs = response.json()
    assert len(defs) >= 10
    
    ids = {d["id"] for d in defs}
    assert "accuracy" in ids
    assert "completeness" in ids
    assert "consistency" in ids
    assert "hallucination_detection" in ids
    assert "outcome_achievement" in ids


def test_register_custom_validation_metric(client):
    """Verify we can register new validation metric definitions dynamically."""
    payload = {
        "id": "custom_rag_faithfulness",
        "metric_name": "Custom RAG Faithfulness",
        "category": "groundedness",
        "description": "Fidelity of retrieved chunks to LLM answer",
        "source_system": "Arize Custom Evaluator"
    }
    response = client.post("/api/validation/metrics", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["id"] == "custom_rag_faithfulness"
    assert res["category"] == "groundedness"

    # Verify list contains it
    defs = client.get("/api/validation/metrics").json()
    ids = {d["id"] for d in defs}
    assert "custom_rag_faithfulness" in ids


def test_configure_and_get_validation_rules(client):
    """Verify we can set validation rules and retrieve them for an agent."""
    agent_id = "rule-agent-test"
    payload = {
        "agent_id": agent_id,
        "metric_id": "accuracy",
        "operator": "gte",
        "threshold": 0.85,
        "enabled": True
    }
    response = client.post("/api/validation/rules", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["agent_id"] == agent_id
    assert res["metric_id"] == "accuracy"
    assert res["operator"] == "gte"
    assert res["threshold"] == 0.85

    # Retrieve rules
    rules = client.get(f"/api/validation/rules/{agent_id}").json()
    assert len(rules) == 1
    assert rules[0]["metric_id"] == "accuracy"


def test_validation_value_ingest_fails_on_unregistered_metric(client):
    """Verify value ingestion fails if validation metric is not registered."""
    payload = {
        "agent_id": "test-agent-val",
        "metric_id": "non_existent_val_metric",
        "value": 1.0,
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z"
    }
    response = client.post("/api/validation/values", json=payload)
    assert response.status_code == 400
    assert "not registered" in response.json()["detail"]


def test_dynamic_validation_scoring_and_gate_trigger(client):
    """Verify validation rule evaluations, scoring changes, and compliance gate triggers."""
    agent_id = "validation-gated-agent"
    start_str = "2026-06-01T00:00:00Z"
    end_str = "2026-06-02T00:00:00Z"

    # 1. Initial ingest: bootstrap agent with zero required validation rules
    initial_payload = {
        "agent_id": agent_id,
        "agent_name": "Validation Gated Agent",
        "period_start": start_str,
        "period_end": end_str,
        "tasks": {"assigned": 5, "completed": 5, "failed": 0},
        "executions": {"attempts": 5, "successful": 5},
        "policy": {"total_actions": 5, "violations": []},
        "validation": {"required_components": 0, "validated_components": 0},
        "cost": {"input_tokens": 100, "output_tokens": 200, "model_cost": 0.01},
        "source": "manual"
    }
    r = client.post("/ingest", json=initial_payload)
    assert r.status_code == 200

    # Initial score: since required=0, V must default to 1.0 (vacuously safe), gate does not fire
    rating = client.get(f"/agents/{agent_id}/score").json()
    assert rating["metrics"]["V"] == 1.0
    assert rating["unsafe"] is False
    assert "V" not in rating["gate_failures"]

    # 2. Configure rules: Accuracy >= 0.85 and Hallucination Detection <= 0.10
    client.post("/api/validation/rules", json={
        "agent_id": agent_id,
        "metric_id": "accuracy",
        "operator": "gte",
        "threshold": 0.85
    })
    client.post("/api/validation/rules", json={
        "agent_id": agent_id,
        "metric_id": "hallucination_detection",
        "operator": "lte",
        "threshold": 0.10
    })

    # 3. Post passing validation run values
    # Ingest accuracy = 0.90 (passes >= 0.85)
    client.post("/api/validation/values", json={
        "agent_id": agent_id,
        "metric_id": "accuracy",
        "value": 0.90,
        "period_start": start_str,
        "period_end": end_str
    })
    # Ingest hallucination = 0.05 (passes <= 0.10)
    client.post("/api/validation/values", json={
        "agent_id": agent_id,
        "metric_id": "hallucination_detection",
        "value": 0.05,
        "period_start": start_str,
        "period_end": end_str
    })

    # Validate calculated summary
    calc_resp = client.get(
        f"/api/validation/agents/{agent_id}/calculate",
        params={"period_start": start_str, "period_end": end_str}
    )
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()
    assert calc_data["validation_score"] == 1.0
    assert calc_data["validated_components"] == 2
    assert calc_data["required_components"] == 2

    # Check that rating score is rescored with V=1.0 and safe
    rating_after = client.get(f"/agents/{agent_id}/score").json()
    assert rating_after["metrics"]["V"] == 1.0
    assert rating_after["unsafe"] is False

    # 4. Ingest failing validation values
    # Ingest accuracy = 0.70 (fails)
    client.post("/api/validation/values", json={
        "agent_id": agent_id,
        "metric_id": "accuracy",
        "value": 0.70,
        "period_start": start_str,
        "period_end": end_str
    })
    # Average accuracy = (0.90 + 0.70) / 2 = 0.80 (still fails >= 0.85)
    # Average hallucination = 0.05 (passes <= 0.10)
    # Only 1 rule passes, so V = 1 / 2 = 0.50

    calc_resp_failing = client.get(
        f"/api/validation/agents/{agent_id}/calculate",
        params={"period_start": start_str, "period_end": end_str}
    )
    assert calc_resp_failing.json()["validation_score"] == 0.50
    assert calc_resp_failing.json()["validated_components"] == 1

    # Check that rating score is rescored with V=0.50, compliance gate triggers!
    rating_failing = client.get(f"/agents/{agent_id}/score").json()
    assert rating_failing["metrics"]["V"] == 0.50
    # Gate triggers (V < 0.60 floor)
    assert rating_failing["unsafe"] is True
    assert "V" in rating_failing["gate_failures"]
    assert rating_failing["score"] <= 69.0
    assert rating_failing["band"] == "Needs Optimization"
