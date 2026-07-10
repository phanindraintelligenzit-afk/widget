from __future__ import annotations

import json
from pathlib import Path


def test_submit_sme_rating(client):
    obs = json.loads((Path(__file__).parent.parent / "fixtures/obs_strong.json").read_text())
    obs.pop("_label", None)
    client.post("/ingest", json=obs)

    r = client.post(
        f"/agents/{obs['agent_id']}/sme-rating",
        json={
            "agent_id": obs["agent_id"],
            "accuracy": 0.91,
            "consistency": 0.88,
            "hallucination_rate": 0.05,
            "submitted_by": "qa@example.com",
        },
    )
    assert r.status_code == 200
    assert "id" in r.json()


def test_sme_rating_id_mismatch_rejected(client):
    r = client.post(
        "/agents/A/sme-rating",
        json={
            "agent_id": "B",
            "accuracy": 0.9, "consistency": 0.9, "hallucination_rate": 0.0,
            "submitted_by": "qa@example.com",
        },
    )
    assert r.status_code == 400
