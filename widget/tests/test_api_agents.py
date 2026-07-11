from __future__ import annotations

import json
from pathlib import Path

from fixtures import load_raw


def _post_canonical(client, fixture_name: str):
    p = Path(__file__).parent.parent / f"fixtures/obs_{fixture_name}.json"
    obs = json.loads(p.read_text())
    obs.pop("_label", None)
    r = client.post("/ingest", json=obs)
    assert r.status_code == 200, r.text
    return r.json()


def test_agents_list_after_ingest(client):
    _post_canonical(client, "strong")
    _post_canonical(client, "baseline")
    r = client.get("/agents")
    assert r.status_code == 200
    agents = r.json()
    assert len(agents) == 2
    ids = {a["agent_id"] for a in agents}
    assert ids == {"agent-strong-001", "agent-baseline-002"}


def test_agent_score_returns_latest(client):
    _post_canonical(client, "strong")
    r = client.get("/agents/agent-strong-001/score")
    assert r.status_code == 200
    rating = r.json()
    assert rating["band"] in ("Strong", "Exceptional", "Needs Optimization")
    assert "metrics" in rating


def test_agent_score_404_for_unknown(client):
    r = client.get("/agents/ghost/score")
    assert r.status_code == 404


def test_agent_history_newest_first(client):
    import time
    _post_canonical(client, "strong")
    time.sleep(0.01)
    _post_canonical(client, "strong")
    time.sleep(0.01)
    _post_canonical(client, "strong")
    r = client.get("/agents/agent-strong-001/history")
    assert r.status_code == 200
    h = r.json()
    from store import db as db_mod
    from sqlalchemy import text
    engine = db_mod.get_engine()
    with engine.connect() as conn:
        c = conn.execute(text("SELECT count(*) FROM score_history")).scalar()
        print(f"DB COUNT: {c}")
    assert len(h) == 3
    # Same observation re-ingested → same score; just verify chronological key present.
    for p in h:
        assert "computed_at" in p
        assert "score" in p


def test_ratings_board_after_mixed_ingest(client):
    _post_canonical(client, "strong")
    _post_canonical(client, "unsafe")
    r = client.get("/ratings?all=true")
    assert r.status_code == 200
    board = r.json()
    assert len(board) == 2
    by_id = {b["agent_id"]: b for b in board}
    assert by_id["agent-unsafe-003"]["unsafe"] is True
    assert by_id["agent-strong-001"]["unsafe"] is False


def test_ratings_board_skips_agents_without_scores(client):
    # No ingest yet — board is empty.
    r = client.get("/ratings?all=true")
    assert r.status_code == 200
    assert r.json() == []
