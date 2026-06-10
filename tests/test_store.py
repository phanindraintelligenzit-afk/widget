from __future__ import annotations

from contract import Rating, Settings
from fixtures import load
from store import configure, get_session_factory, init_db, repo


def _session():
    return get_session_factory()()


def setup_function(_):
    # Each test gets a fresh in-memory DB.
    from store import db as db_mod
    db_mod._engine = None  # type: ignore[attr-defined]
    db_mod._SessionLocal = None  # type: ignore[attr-defined]
    configure("sqlite:///:memory:")
    init_db()


def test_upsert_agent_creates_then_updates():
    s = _session()
    a1 = repo.upsert_agent(s, "a", "Agent A", baseline=80.0)
    assert a1.id == "a"
    assert a1.baseline_human_output == 80.0
    a2 = repo.upsert_agent(s, "a", "Agent A v2", baseline=120.0)
    assert a2 is a1
    assert a2.name == "Agent A v2"
    assert a2.baseline_human_output == 120.0
    s.commit()


def test_upsert_agent_uses_default_baseline_1_0():
    """Default baseline should be 1.0 when none provided."""
    s = _session()
    agent = repo.upsert_agent(s, "default-agent", "Default Agent")
    assert agent.baseline_human_output == 1.0
    s.commit()


def test_save_observation_and_score_round_trip():
    s = _session()
    obs = load("strong")
    repo.upsert_agent(s, obs.agent_id, obs.agent_name)
    obs_row = repo.save_observation(s, obs)
    rating = Rating(
        score=88.0, raw_score=88.0, band="Exceptional", unsafe=False,
        gate_failures=[], metrics={"P": 1.0, "Q": 0.9}, missing=[],
    )
    score_row = repo.save_score(s, obs.agent_id, obs_row.id, rating)
    s.commit()
    assert score_row.id is not None

    latest = repo.latest_score(s, obs.agent_id)
    assert latest is not None
    assert latest.score == 88.0
    assert latest.band == "Exceptional"

    history = repo.score_history(s, obs.agent_id)
    assert len(history) == 1


def test_score_history_orders_newest_first():
    s = _session()
    obs = load("strong")
    repo.upsert_agent(s, obs.agent_id, obs.agent_name)
    obs_row = repo.save_observation(s, obs)
    for score in (70.0, 80.0, 90.0):
        r = Rating(score=score, raw_score=score, band="Strong", unsafe=False,
                   gate_failures=[], metrics={}, missing=[])
        repo.save_score(s, obs.agent_id, obs_row.id, r)
    s.commit()
    history = repo.score_history(s, obs.agent_id)
    assert [h.score for h in history] == [90.0, 80.0, 70.0]


def test_settings_round_trip():
    s = _session()
    assert repo.get_settings(s).r_max == 3.0
    custom = Settings(r_max=42.0, utilization=0.9, human_cost_per_output=2.0)
    repo.save_settings(s, custom)
    s.commit()
    assert repo.get_settings(s).r_max == 42.0
    assert repo.get_settings(s).utilization == 0.9


def test_latest_scores_for_all_skips_agents_without_scores():
    s = _session()
    repo.upsert_agent(s, "no-score-agent", "Lonely Agent")
    s.commit()
    rows = repo.latest_scores_for_all(s)
    assert len(rows) == 1
    assert rows[0][1] is None  # no score yet
