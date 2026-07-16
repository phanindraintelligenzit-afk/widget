import sys
import json
from fastapi.testclient import TestClient

from api.app import app

def main():
    obs = {
        "agent_id": "e2e-agent",
        "agent_name": "E2E",
        "period_start": "2023-01-01T00:00:00Z",
        "period_end": "2023-01-01T00:00:00Z",
        "tasks": {"assigned": 1, "completed": 1, "failed": 0},
        "executions": {"attempts": 1, "successful": 1},
        "policy": {"total_actions": 1, "violations": []},
        "incidents": [],
        "validation": {"required_components": 1, "validated_components": 1},
        "cost": {"input_tokens": 1, "output_tokens": 1, "model_cost": 1.0, "number_of_llm_calls": 1, "Human_cost": 0.0},
        "source": "test"
    }
    
    from store import db
    db.configure("sqlite:///:memory:")
    db.init_db()

    with TestClient(app) as client:
        r = client.post("/ingest", json=obs)
        print(f"Ingest Status: {r.status_code}")
        
        r2 = client.get("/agents/e2e-agent/score")
        print(f"Score Status: {r2.status_code}")
        print(r2.text)

if __name__ == "__main__":
    main()
