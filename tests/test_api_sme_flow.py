"""SME conversational quality capture through the HTTP surface.

The closed loop: source partials leave Q deferred → SME walks the
flow → score reflects Q.
"""
from __future__ import annotations

from fixtures import load_source


def _seed_with_q_deferred(client) -> str:
    """Push AWS cost only — produces an agent with everything but C deferred."""
    client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    return "agent-multi-001"


def _walk(client, agent_id, answers):
    r = client.post(
        "/sme-flow/start",
        json={"agent_id": agent_id, "submitted_by": "qa@example.com"},
    )
    assert r.status_code == 200, r.text
    state = r.json()
    sid = state["session_id"]
    for ans in answers:
        r = client.post(f"/sme-flow/{sid}/respond", json={"response": ans})
        assert r.status_code == 200, r.text
        state = r.json()
    return sid, state


def test_start_returns_first_prompt_and_field(client):
    agent_id = _seed_with_q_deferred(client)
    r = client.post(
        "/sme-flow/start",
        json={"agent_id": agent_id, "submitted_by": "qa@example.com"},
    )
    body = r.json()
    assert body["step"] == "ask_accuracy"
    assert "0–100" in body["prompt"]
    assert body["complete"] is False
    assert body["captured"] == {"accuracy": None, "consistency": None, "hallucination_rate": None}


def test_full_yes_path_persists_and_rescores(client):
    agent_id = _seed_with_q_deferred(client)

    # Before SME input: Q is missing.
    before = client.get(f"/agents/{agent_id}/score").json()
    assert "Q" in before["missing"]
    assert before["metrics"]["Q"] is None

    _, final = _walk(client, agent_id, ["93", "91", "5", "yes"])
    assert final["committed"] is True
    assert final["complete"] is True
    assert final["rating"] is not None
    assert final["rating"]["metrics"]["Q"] is not None

    # Latest score reflects the committed Q.
    after = client.get(f"/agents/{agent_id}/score").json()
    assert "Q" not in after["missing"]
    assert after["metrics"]["Q"] is not None


def test_review_no_does_not_persist(client):
    agent_id = _seed_with_q_deferred(client)
    _, final = _walk(client, agent_id, ["80", "75", "10", "no"])
    assert final["committed"] is False
    assert final["complete"] is True
    assert final["rating"] is None

    after = client.get(f"/agents/{agent_id}/score").json()
    assert "Q" in after["missing"]  # still deferred


def test_invalid_input_keeps_session_on_same_step(client):
    agent_id = _seed_with_q_deferred(client)
    r = client.post(
        "/sme-flow/start",
        json={"agent_id": agent_id, "submitted_by": "qa@example.com"},
    )
    sid = r.json()["session_id"]
    r2 = client.post(f"/sme-flow/{sid}/respond", json={"response": "abc"})
    body = r2.json()
    assert body["step"] == "ask_accuracy"
    assert body["error"] is not None
    assert body["captured"]["accuracy"] is None


def test_unknown_session_returns_404(client):
    r = client.post("/sme-flow/no-such-session/respond", json={"response": "hi"})
    assert r.status_code == 404
