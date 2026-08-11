from __future__ import annotations


def test_settings_default(client):
    r = client.get("/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["r_max"] == 50.0
    assert body["weights"]["P"] == 0.15


def test_settings_update_persists(client):
    payload = {
        "weights": {"P": 0.15, "Q": 0.20, "E": 0.15, "G": 0.20, "R": 0.15, "V": 0.10, "C": 0.05},
        "q_sub_weights": {"accuracy": 0.7, "consistency": 0.2, "hallucination": 0.1},
        "gate_thresholds": {"G": 0.70, "R": 0.60, "V": 0.70},
        "r_max": 25.0,
        "human_cost_per_output": 2.5,
        "utilization": 0.8,
    }
    r = client.put("/settings", json=payload)
    assert r.status_code == 200
    assert r.json()["r_max"] == 25.0

    r2 = client.get("/settings")
    assert r2.json()["gate_thresholds"]["G"] == 0.70


def test_updated_gate_thresholds_actually_apply_to_scoring(client):
    # Tighten G threshold to 0.95 so the strong fixture (G=1.0 is fine, but
    # baseline G ~= 0.99) still passes — pick a value that makes a fixture trip.
    payload = {
        "weights": {"P": 0.15, "Q": 0.20, "E": 0.15, "G": 0.20, "R": 0.15, "V": 0.10, "C": 0.05},
        "q_sub_weights": {"accuracy": 0.7, "consistency": 0.2, "hallucination": 0.1},
        "gate_thresholds": {"G": 1.01, "R": 0.50, "V": 0.60},  # impossible-to-meet G
        "r_max": 3.0,
        "human_cost_per_output": 1.0,
        "utilization": 1.0,
    }
    client.put("/settings", json=payload)

    import json
    from pathlib import Path
    obs = json.loads((Path(__file__).parent.parent / "fixtures/obs_strong.json").read_text())
    obs.pop("_label", None)
    r = client.post("/ingest", json=obs)
    assert r.status_code == 200
    assert r.json()["unsafe"] is True
    assert "G" in r.json()["gate_failures"]
