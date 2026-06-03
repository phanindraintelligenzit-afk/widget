"""End-to-end via the API: one agent assembled live from five sources."""
from __future__ import annotations

from fixtures import load_source


def test_sources_listed_at_startup(client):
    r = client.get("/sources")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    # 5 real + 5 stub sources.
    assert {"aws_cost", "puvi_noise", "arize", "servicenow", "jira"}.issubset(names)
    assert {"langgraph", "bedrock", "ray", "bmc", "sap_hr"}.issubset(names)


def test_aws_cost_alone_produces_C_dominated_rating(client):
    r = client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    assert r.status_code == 200, r.text
    [rating] = r.json()
    # Only C is populated; the engine deferred the rest.
    assert set(rating["missing"]) == {"P", "Q", "E", "G", "R", "V"}
    assert rating["metrics"]["C"] is not None
    assert 0 < rating["score"] <= 100


def test_unknown_source_returns_404(client):
    r = client.post("/ingest/source/no-such-source", json={})
    assert r.status_code == 404


def test_multi_source_story_one_agent_assembled_from_five_sources(client):
    """The headline M5 demo: one agent, no single canonical observation,
    five independent source feeds. Each POST re-merges and re-scores."""
    AGENT = "agent-multi-001"

    # 1. AWS Cost arrives first — C only.
    r1 = client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    rating_after_cost = r1.json()[0]
    assert rating_after_cost["metrics"]["C"] is not None
    assert rating_after_cost["metrics"]["G"] is None
    assert rating_after_cost["metrics"]["R"] is None

    # 2. Puvi noise lands — G appears.
    client.post("/ingest/source/puvi_noise", json=load_source("puvi_noise"))
    r_after_puvi = client.get(f"/agents/{AGENT}/score").json()
    assert r_after_puvi["metrics"]["G"] is not None
    assert r_after_puvi["metrics"]["C"] is not None  # still there from earlier partial

    # 3. Arize lands — Q appears, G is overwritten by the more-recent source.
    client.post("/ingest/source/arize", json=load_source("arize"))
    r_after_arize = client.get(f"/agents/{AGENT}/score").json()
    assert r_after_arize["metrics"]["Q"] is not None

    # 4. ServiceNow + Jira → R appears (Jira lands last so it wins).
    client.post("/ingest/source/servicenow", json=load_source("servicenow"))
    client.post("/ingest/source/jira", json=load_source("jira"))
    r_final = client.get(f"/agents/{AGENT}/score").json()
    assert r_final["metrics"]["R"] is not None

    # Only the dimensions no source in this M5 set speaks to remain missing:
    # P (tasks), E (executions), V (validation). All three are agent-runtime
    # dimensions — they show up once a LangGraph/Bedrock/etc. adapter is wired.
    assert set(r_final["missing"]) == {"P", "E", "V"}
    assert r_final["metrics"]["C"] is not None  # aws_cost
    assert r_final["metrics"]["G"] is not None  # arize (latest, overwrote puvi)
    assert r_final["metrics"]["Q"] is not None  # arize
    assert r_final["metrics"]["R"] is not None  # jira (latest, overwrote servicenow)
    assert r_final["unsafe"] is False
    assert 0 < r_final["score"] <= 100

    # History grew with each ingest (one score per affected partial).
    history = client.get(f"/agents/{AGENT}/history").json()
    assert len(history) >= 5


def test_servicenow_payload_scores_each_distinct_agent(client):
    # Fixture has two distinct agents; expect two ratings back.
    r = client.post("/ingest/source/servicenow", json=load_source("servicenow"))
    assert r.status_code == 200
    out = r.json()
    assert len(out) == 2
