from __future__ import annotations

import json
from pathlib import Path

from fixtures import load_otel_spans, load_raw


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


def test_ingest_via_otel_adapter(client):
    spans = load_otel_spans()
    r = client.post("/ingest/otel", json=spans)
    assert r.status_code == 200, r.text
    out = r.json()
    assert isinstance(out, list)
    assert len(out) == 1
    assert "score" in out[0]


def test_ingest_via_webhook_adapter_acme(client):
    payload = load_raw("acme_payload")
    r = client.post("/ingest/webhook:acme", json=payload)
    assert r.status_code == 200, r.text
    out = r.json()
    assert len(out) == 1
    assert 0 < out[0]["score"] <= 100


def test_ingest_unknown_adapter_returns_404(client):
    r = client.post("/ingest/does-not-exist", json={})
    assert r.status_code == 404


def test_ingest_malformed_observation_returns_422(client):
    r = client.post("/ingest", json={"agent_id": "x"})  # missing required fields
    assert r.status_code == 422
