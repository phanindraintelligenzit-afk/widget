import httpx
import time

base_url = "http://127.0.0.1:8000"

def run_e2e():
    print("--- 1. Onboard Agent ---")
    agent_id = "test-agent-e2e-001"
    r = httpx.post(f"{base_url}/api/agents/{agent_id}/onboard", json={
        "description": "E2E Test Agent",
        "agent_type": "Integration",
        "environment": "Test",
        "business_owner_name": "Test Owner",
        "business_owner_email": "test@test.com",
        "technical_owner_name": "Tech Owner",
        "technical_owner_email": "tech@test.com"
    })
    print(f"Onboard Status: {r.status_code}")
    assert r.status_code == 200
    
    print("\n--- 2. Save Configuration ---")
    # Change Base, Multipliers, Powers, and Weightages
    configs = {
        "Base_P": "0.9", "Multiplier_P": "2.0", "Power_P": "1.0", "Weight_P": "30",
        "Base_Q": "0.8", "Multiplier_Q": "1.0", "Power_Q": "2.0", "Weight_Q": "20",
        "Base_E": "0.7", "Multiplier_E": "1.5", "Power_E": "1.0", "Weight_E": "10",
        "Base_G": "0.6", "Multiplier_G": "1.0", "Power_G": "1.5", "Weight_G": "10",
        "Base_R": "0.5", "Multiplier_R": "1.0", "Power_R": "2.0", "Weight_R": "10",
        "Base_C": "0.4", "Multiplier_C": "1.0", "Power_C": "1.0", "Weight_C": "10",
        "Base_V": "0.3", "Multiplier_V": "1.0", "Power_V": "1.0", "Weight_V": "10"
    }
    
    for k, v in configs.items():
        r = httpx.post(f"{base_url}/api/agents/{agent_id}/config", json={
            "configuration_key": k,
            "configuration_value": str(v),
            "source": "E2E Script"
        })
        assert r.status_code == 200
    print("Configuration Saved Successfully")
    
    print("\n--- 3. Send Telemetry ---")
    # Send some raw telemetry to trigger score calculation
    telemetry = {
        "productivity": {"normalization_factor": 1.0, "human_baseline": 10.0, "effective_output": 9.0},
        "quality": {"accuracy": 0.8, "consistency": 0.8, "hallucination_rate": 0.1},
        "executions": {"trace_captured": True},
        "policy": {"Total Actions": 10, "Policy Violations": 4}, # G = 0.6
    }
    r = httpx.post(f"{base_url}/api/ingest/{agent_id}/telemetry", json=telemetry)
    print(f"Telemetry Status: {r.status_code}")
    assert r.status_code in (200, 202)
    
    print("\n--- 4. Verify Dashboard & Final Score ---")
    r = httpx.get(f"{base_url}/ratings")
    ratings = r.json()
    my_agent = next((a for a in ratings if a["agent_id"] == agent_id), None)
    assert my_agent is not None
    print(f"Agent Found in Dashboard! Final Score: {my_agent['score']} | Raw: {my_agent['raw_score']}")
    print(f"Sub-Metrics: P={my_agent['metrics'].get('P')}, Q={my_agent['metrics'].get('Q')}")
    
    print("\n--- E2E SUCCESS ---")

run_e2e()
