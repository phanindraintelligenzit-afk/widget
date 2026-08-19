"""Sanity-check that fixtures parse into the canonical contract and that
the engine produces sensible ratings from them. No hard reference numbers
here — those live in test_engine_reference.py.
"""
from __future__ import annotations

from contract import AgentBaseline, Settings
from engine import metrics_from_observation, rate
from fixtures import all_observations, load


def test_all_fixtures_parse():
    obs = all_observations()
    assert {"strong", "baseline", "unsafe"}.issubset(obs.keys())
    for o in obs.values():
        assert o.agent_id
        assert o.tasks.assigned >= o.tasks.completed - o.tasks.pending_approval


def test_strong_fixture_rates_well():
    obs = load("strong")
    settings = Settings(gate_thresholds={"G": 0.60, "R": 0.70, "V": 0.60}, q_sub_weights={"accuracy": 0.70, "consistency": 0.20, "hallucination": 0.10}, r_max=10.0, human_cost_per_output=1.50, utilization=0.95)
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=100.0)
    m = metrics_from_observation(obs, settings, baseline)
    r = rate(m)
    assert r.unsafe is False
    assert r.band in ("Strong", "Exceptional")


def test_baseline_fixture_defers_Q():
    obs = load("baseline")
    settings = Settings(gate_thresholds={"G": 0.60, "R": 0.70, "V": 0.60}, q_sub_weights={"accuracy": 0.70, "consistency": 0.20, "hallucination": 0.10}, r_max=50.0)
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=100.0)
    m = metrics_from_observation(obs, settings, baseline)
    assert m["Q"] is None
    r = rate(m)
    assert "Q" in r.missing


def test_unsafe_fixture_trips_G_gate():
    obs = load("unsafe")
    settings = Settings(gate_thresholds={"G": 0.60, "R": 0.70, "V": 0.60}, q_sub_weights={"accuracy": 0.70, "consistency": 0.20, "hallucination": 0.10}, r_max=50.0)
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=100.0)
    m = metrics_from_observation(obs, settings, baseline)
    r = rate(m)
    assert r.unsafe is True
    assert "G" in r.gate_failures
    assert r.band == "Needs Optimization"
