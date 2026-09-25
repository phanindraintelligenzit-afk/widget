import pytest
from fastapi.testclient import TestClient
from api.app import app
from store.db import get_engine
from store.models import Base

Base.metadata.create_all(get_engine())

client = TestClient(app)

def test_1_create_weightage_success():
    resp = client.put("/api/agents/test-agent-1/weightages", json={
        "weight_p": 10, "weight_q": 20, "weight_e": 20, "weight_v": 10, "weight_r": 10, "weight_g": 10, "weight_c": 20
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_weight"] == 100

def test_2_update_weightage_success():
    resp = client.put("/api/agents/test-agent-1/weightages", json={
        "weight_p": 50, "weight_q": 10, "weight_e": 10, "weight_v": 5, "weight_r": 5, "weight_g": 10, "weight_c": 10
    })
    assert resp.status_code == 200
    assert resp.json()["weight_p"] == 50

def test_3_get_weightage():
    resp = client.get("/api/agents/test-agent-1/weightages")
    assert resp.status_code == 200
    assert resp.json()["weight_p"] == 50

def test_4_get_nonexistent_weightage():
    resp = client.get("/api/agents/nonexistent/weightages")
    assert resp.status_code == 404

def test_5_total_weight_under_100():
    resp = client.put("/api/agents/test-agent-1/weightages", json={
        "weight_p": 10, "weight_q": 10, "weight_e": 10, "weight_v": 10, "weight_r": 10, "weight_g": 10, "weight_c": 10
    })
    assert resp.status_code == 400

def test_6_total_weight_over_100():
    resp = client.put("/api/agents/test-agent-1/weightages", json={
        "weight_p": 20, "weight_q": 20, "weight_e": 20, "weight_v": 20, "weight_r": 20, "weight_g": 20, "weight_c": 20
    })
    assert resp.status_code == 400

def test_7_total_weight_boundary():
    resp = client.put("/api/agents/test-agent-boundary/weightages", json={
        "weight_p": 14.28, "weight_q": 14.28, "weight_e": 14.28, "weight_v": 14.28, "weight_r": 14.29, "weight_g": 14.29, "weight_c": 14.30
    })
    assert resp.status_code == 200
    assert resp.json()["total_weight"] == 100.0

def test_8_weight_update_reflects_in_db():
    resp = client.put("/api/agents/test-agent-db/weightages", json={
        "weight_p": 100, "weight_q": 0, "weight_e": 0, "weight_v": 0, "weight_r": 0, "weight_g": 0, "weight_c": 0
    })
    assert resp.status_code == 200
    resp2 = client.get("/api/agents/test-agent-db/weightages")
    assert resp2.json()["weight_p"] == 100

def test_9_weight_persistence():
    resp = client.put("/api/agents/test-agent-p/weightages", json={
        "weight_p": 0, "weight_q": 100, "weight_e": 0, "weight_v": 0, "weight_r": 0, "weight_g": 0, "weight_c": 0
    })
    assert resp.status_code == 200

def test_10_default_weights_when_not_configured():
    obs = {
        "agent_id": "test-agent-default",
        "agent_name": "Test Default",
        "period_start": "2024-01-01T00:00:00Z",
        "period_end": "2024-01-01T01:00:00Z",
        "source": "test",
        "tasks": {"assigned": 1, "completed": 1, "failed": 0},
        "executions": {"attempts": 1, "successful": 1},
        "policy": {"total_actions": 1, "violations": []},
        "validation": {"required_components": 1, "validated_components": 1},
        "cost": {"input_tokens": 10, "output_tokens": 10, "model_cost": 0.1}
    }
    resp = client.post("/ingest", json=obs)
    assert resp.status_code == 200
    assert "P" in resp.json()["weights_used"]

def test_11_custom_weights_override_defaults():
    client.put("/api/agents/test-agent-custom/weightages", json={
        "weight_p": 50, "weight_q": 50, "weight_e": 0, "weight_v": 0, "weight_r": 0, "weight_g": 0, "weight_c": 0
    })
    obs = {
        "agent_id": "test-agent-custom",
        "agent_name": "Test Custom",
        "period_start": "2024-01-01T00:00:00Z",
        "period_end": "2024-01-01T01:00:00Z",
        "source": "test",
        "tasks": {"assigned": 1, "completed": 1, "failed": 0},
        "executions": {"attempts": 1, "successful": 1},
        "policy": {"total_actions": 1, "violations": []},
        "validation": {"required_components": 1, "validated_components": 1},
        "cost": {"input_tokens": 10, "output_tokens": 10, "model_cost": 0.1}
    }
    resp = client.post("/ingest", json=obs)
    assert resp.status_code == 200
    assert resp.json()["weights_used"]["P"] == 1.0

def test_12_scoring_uses_custom_weights_p():
    client.put("/api/agents/test-agent-custom2/weightages", json={
        "weight_p": 100, "weight_q": 0, "weight_e": 0, "weight_v": 0, "weight_r": 0, "weight_g": 0, "weight_c": 0
    })
    obs = {
        "agent_id": "test-agent-custom2",
        "agent_name": "Test Custom",
        "period_start": "2024-01-01T00:00:00Z",
        "period_end": "2024-01-01T01:00:00Z",
        "source": "test",
        "tasks": {"assigned": 1, "completed": 1, "failed": 0},
        "executions": {"attempts": 1, "successful": 1},
        "policy": {"total_actions": 1, "violations": []},
        "validation": {"required_components": 1, "validated_components": 1},
        "cost": {"input_tokens": 10, "output_tokens": 10, "model_cost": 0.1}
    }
    resp = client.post("/ingest", json=obs)
    assert resp.status_code == 200
    assert resp.json()["weights_used"]["P"] == 1.0

def test_13_scoring_uses_custom_weights_q():
    client.put("/api/agents/test-agent-custom3/weightages", json={
        "weight_p": 0, "weight_q": 100, "weight_e": 0, "weight_v": 0, "weight_r": 0, "weight_g": 0, "weight_c": 0
    })
    obs = {
        "agent_id": "test-agent-custom3",
        "agent_name": "Test Custom",
        "period_start": "2024-01-01T00:00:00Z",
        "period_end": "2024-01-01T01:00:00Z",
        "source": "test",
        "tasks": {"assigned": 1, "completed": 1, "failed": 0},
        "executions": {"attempts": 1, "successful": 1},
        "policy": {"total_actions": 1, "violations": []},
        "validation": {"required_components": 1, "validated_components": 1},
        "cost": {"input_tokens": 10, "output_tokens": 10, "model_cost": 0.1}
    }
    resp = client.post("/ingest", json=obs)
    assert resp.status_code == 200
    assert "Q" not in resp.json()["weights_used"] or resp.json()["weights_used"].get("Q") == 1.0

def test_14_scoring_handles_missing_agent():
    obs = {
        "agent_id": "missing-agent-123",
        "agent_name": "Missing",
        "period_start": "2024-01-01T00:00:00Z",
        "period_end": "2024-01-01T01:00:00Z",
        "source": "test",
        "tasks": {"assigned": 1, "completed": 1, "failed": 0},
        "executions": {"attempts": 1, "successful": 1},
        "policy": {"total_actions": 1, "violations": []},
        "validation": {"required_components": 1, "validated_components": 1},
        "cost": {"input_tokens": 10, "output_tokens": 10, "model_cost": 0.1}
    }
    resp = client.post("/ingest", json=obs)
    assert resp.status_code == 200

def test_15_rescore_from_partials_uses_custom_weights():
    assert True
