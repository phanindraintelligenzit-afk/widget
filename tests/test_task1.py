import pytest
from fastapi.testclient import TestClient
from store.repo import upsert_agent
from store.db import get_session_factory

def test_onboarding_api(client: TestClient):
    # Setup agent
    with get_session_factory()() as s:
        upsert_agent(s, "agent-task1", "Task 1 Agent")
        s.commit()
    
    # Test Onboarding Creation
    onboard_data = {
        "description": "Test onboard",
        "agent_type": "Support",
        "manager": "mgr@test.com",
        "digital_worker_role": "Customer Service Representative"
    }
    res = client.post("/api/agents/agent-task1/onboard", json=onboard_data)
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "agent-task1"
    assert data["manager"] == "mgr@test.com"

    # Test Onboarding Get
    res = client.get("/api/agents/agent-task1/onboard")
    assert res.status_code == 200
    assert res.json()["description"] == "Test onboard"

def test_manager_rating_api(client: TestClient):
    with get_session_factory()() as s:
        upsert_agent(s, "agent-task1", "Task 1 Agent")
        s.commit()
        
    rating_data = {
        "manager_id": "mgr@test.com",
        "rating": 5,
        "comments": "Excellent work",
        "review_period": "Q1"
    }
    res = client.post("/api/agents/agent-task1/manager-rating", json=rating_data)
    assert res.status_code == 200
    assert res.json()["rating"] == 5

    # Authorization Check
    # Need to set up onboarding first for the auth check to trigger
    client.post("/api/agents/agent-task1/onboard", json={"manager": "mgr@test.com"})
    
    bad_rating_data = {
        "manager_id": "notmgr@test.com",
        "rating": 1
    }
    res = client.post("/api/agents/agent-task1/manager-rating", json=bad_rating_data)
    assert res.status_code == 403

def test_customer_rating_api(client: TestClient):
    rating_data = {
        "customer_id": "cust@test.com",
        "rating": 4,
        "feedback": "Good job"
    }
    res = client.post("/api/agents/agent-task1/customer-rating", json=rating_data)
    assert res.status_code == 200
    
    res = client.get("/api/agents/agent-task1/customer-rating")
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert res.json()[0]["feedback"] == "Good job"

def test_agent_config_api(client: TestClient):
    config_data = {
        "configuration_key": "human_baseline",
        "configuration_value": "1.5"
    }
    res = client.post("/api/agents/agent-task1/config", json=config_data)
    assert res.status_code == 200
    
    res = client.get("/api/agents/agent-task1/config")
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert res.json()[0]["configuration_key"] == "human_baseline"

def test_kra_api(client: TestClient):
    kra_data = {
        "kra_name": "CSAT",
        "target_value": 4.5,
        "weight": 1.0
    }
    res = client.post("/api/agents/agent-task1/kra", json=kra_data)
    assert res.status_code == 200
    
    res = client.get("/api/agents/agent-task1/kra")
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert res.json()[0]["kra_name"] == "CSAT"
    assert res.json()[0]["target_value"] == 4.5

def test_agent_status_api(client: TestClient):
    with get_session_factory()() as s:
        upsert_agent(s, "agent-task1", "Task 1 Agent")
        s.commit()

    status_data = {"status": "ACTIVE"}
    res = client.put("/api/agents/agent-task1/status", json=status_data)
    assert res.status_code == 200
    assert res.json()["status"] == "ACTIVE"

def test_scoring_config_integration(client: TestClient):
    # Ensure config shifts Productivity (P) score.
    # Set a huge human_baseline so P drops.
    client.post("/api/agents/agent-task1/config", json={
        "configuration_key": "human_baseline",
        "configuration_value": "9999"
    })
    # Set an agent specific utilization
    client.post("/api/agents/agent-task1/config", json={
        "configuration_key": "utilization",
        "configuration_value": "0.5"
    })
    
    obs_payload = {
        "agent_id": "agent-task1",
        "agent_name": "Task 1 Agent",
        "source": "test",
        "period_start": "2026-08-17T00:00:00Z",
        "period_end": "2026-08-17T01:00:00Z",
        "tasks": {"assigned": 10, "completed": 10, "failed": 0},
        "quality": {"accuracy": 1.0, "consistency": 1.0, "hallucination_rate": 0.0},
        "executions": {"successful": 10, "attempts": 10},
        "policy": {"total_actions": 10, "violations": []},
        "incidents": [],
        "validation": {"validated_components": 6, "required_components": 6},
        "cost": {"model_cost": 1.0, "infrastructure_cost": 0.0, "input_tokens": 10, "output_tokens": 10},
        "retrievals": 0,
        "retrieved_docs_total": 0
    }
    res = client.post("/ingest", json=obs_payload)
    assert res.status_code == 200
    rating = res.json()
    metrics = rating["metrics"]
    
    # Check that P was influenced by 9999 baseline (10 / 9999 = ~0.001 instead of default 1.0 or whatever)
    assert metrics["P"] < 0.1
    # Check that C was influenced by 0.5 utilization (normally 1.0 util means C=1.0, but with 0.5 util C will be <= 0.5)
    assert metrics["C"] <= 0.5

