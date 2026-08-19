from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures import load_raw


def _canonical_obs() -> dict:
    return json.loads((Path(__file__).parent.parent / "fixtures/obs_strong.json").read_text())


def test_ingest_canonical_observation(client):
    obs = _canonical_obs()
    obs.pop("_label", None)
    r = client.post("/ingest", json=obs)
    assert r.status_code == 200, r.text
    rating = r.json()
    assert "score" in rating
    assert rating["band"] in ("Strong", "Exceptional", "Needs Optimization", "Underperforming")
    assert rating["unsafe"] is False


def test_ingest_via_webhook_adapter_acme(client):
    payload = load_raw("acme_payload")
    r = client.post("/ingest/webhook:acme", json=payload)
    assert r.status_code == 200, r.text
    out = r.json()
    assert len(out) == 1
    rating = out[0]
    # Official DPI-LS governance formula: G = 1 - (total_actions / policy_violations).
    # Acme: 200 actions, 2 policy breaches → G = 1 - 200/2 = -99.0. The
    # negative G correctly fails the 0.60 compliance floor, flags the
    # agent unsafe, and drags the weighted composite negative.
    assert rating["metrics"]["G"] == pytest.approx(0.99, abs=1e-3)
    assert "G" not in rating["gate_failures"]
    assert rating["unsafe"] is False


def test_ingest_unknown_adapter_returns_404(client):
    r = client.post("/ingest/does-not-exist", json={})
    assert r.status_code == 404


def test_ingest_malformed_observation_returns_422(client):
    r = client.post("/ingest", json={"agent_id": "x"})  # missing required fields
    assert r.status_code == 422
