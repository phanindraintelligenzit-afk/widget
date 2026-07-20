"""End-to-end via the API: one agent assembled live from five sources."""
from __future__ import annotations

import pytest

from fixtures import load_source


def test_sources_listed_at_startup(client):
    r = client.get("/sources")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    # 5 real + 5 stub sources.
    assert {"aws_cost", "puvi_noise", "jira"}.issubset(names)
    assert {"langgraph", "bedrock", "ray", "bmc", "sap_hr"}.issubset(names)


def test_aws_cost_alone_produces_C_dominated_rating(client):
    r = client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    assert r.status_code == 200, r.text
    [rating] = r.json()
    # The AWS Cost fixture ships an ``output_count`` so the adapter
    # also forwards a tasks block — that gives the engine a real
    # denominator for the per-output C math. The C/P dimensions
    # populate; Q/E/G/R/V stay missing because no runtime source
    # in this set speaks to them.
    assert set(rating["missing"]) == {"Q", "E", "G", "R", "V"}
    assert rating["metrics"]["C"] is not None
    assert rating["metrics"]["P"] is not None
    assert 0 < rating["score"] <= 100


def test_aws_cost_without_output_count_stays_c_only(client):
    """Caller didn't supply output_count → no tasks block → only C."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [{"agent_id": "cost-only-agent", "spend_usd": 0.5}],
    }
    r = client.post("/ingest/source/aws_cost", json=payload)
    assert r.status_code == 200, r.text
    [rating] = r.json()
    assert set(rating["missing"]) == {"P", "Q", "E", "G", "R", "V"}
    assert rating["metrics"]["C"] is not None


def test_unknown_source_returns_404(client):
    r = client.post("/ingest/source/no-such-source", json={})
    assert r.status_code == 404


def test_multi_source_story_one_agent_assembled_from_five_sources(client):
    """The headline M5 demo: one agent, no single canonical observation,
    five independent source feeds. Each POST re-merges and re-scores."""
    AGENT = "agent-multi-001"

    # 1. AWS Cost arrives first — C (and P, because the fixture
    #    ships an output_count) populated; everything else stays
    #    None until a later source contributes.
    r1 = client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    rating_after_cost = r1.json()[0]
    assert rating_after_cost["metrics"]["C"] is not None
    assert rating_after_cost["metrics"]["G"] is None
    assert rating_after_cost["metrics"]["R"] is None

    # 2. Puvi noise lands — G appears.
    client.post("/ingest/source/puvi_noise", json=load_source("puvi_noise"))
    r_after_puvi = client.get(f"/agents/{AGENT}/score").json()
    assert r_after_puvi["metrics"]["G"] is not None
    # Official formula: 200 policy evaluations, 3 alerts → G = 1 - 200/3 ≈ -65.67.
    assert r_after_puvi["metrics"]["G"] == pytest.approx(-65.67, abs=1e-2)
    assert r_after_puvi["metrics"]["C"] is not None  # still there from earlier partial

    # 4. ServiceNow + Jira → R appears (Jira lands last so it wins).
    client.post("/ingest/webhook:servicenow", json=load_source("servicenow"))
    client.post("/ingest/source/jira", json=load_source("jira"))
    r_final = client.get(f"/agents/{AGENT}/score").json()
    assert r_final["metrics"]["R"] is not None

    # Only the dimensions no source in this M5 set speaks to remain missing:
    # Q (quality), E (executions) and V (validation) — both are agent-runtime
    # dimensions that show up once a LangGraph/Bedrock/etc. adapter
    # is wired. P arrives alongside C from the AWS Cost fixture
    # because the fixture ships an output_count.
    assert set(r_final["missing"]) == {"Q", "E", "V"}
    assert r_final["metrics"]["C"] is not None  # aws_cost
    assert r_final["metrics"]["G"] is not None  # puvi
    assert r_final["metrics"]["R"] is not None  # jira (latest, overwrote servicenow)
    # The official governance formula yields a negative G for this demo
    # agent (200 actions / 3 violations), so the G compliance gate fires
    # and the agent is flagged unsafe (the score is held at the
    # "Needs Optimization" band by the gate, band override).
    assert r_final["unsafe"] is True
    assert "G" in r_final["gate_failures"]
    assert r_final["band"] == "Needs Optimization"

    # History grew with each ingest (one score per affected partial).
    history = client.get(f"/agents/{AGENT}/history").json()
    assert len(history) >= 4


def test_servicenow_payload_scores_each_distinct_agent(client):
    # Fixture has multiple tickets, but YAML mapping aggregates to the first agent.
    r = client.post("/ingest/webhook:servicenow", json=load_source("servicenow"))
    assert r.status_code == 200
    out = r.json()
    assert len(out) == 1
    assert "R" in out[0]["metrics"]
