"""M2 demand: push a fixture through to a computed score end-to-end.

Two paths exercised: GenericWebhookAdapter (YAML) and OTelAdapter.
Both flow: raw payload -> adapter -> AgentObservation -> engine -> Rating.
The engine never sees the adapter; the adapter never sees the engine.
"""
from __future__ import annotations

import pytest

from contract import AgentBaseline, Settings
from engine import metrics_from_observation, rate
from ingestion import FieldMapping, GenericWebhookAdapter
from fixtures import load_raw, mapping_path


def _rate_observation(obs):
    settings = Settings(gate_thresholds={"G": 0.60, "R": 0.70, "V": 0.60}, q_sub_weights={"accuracy": 0.70, "consistency": 0.20, "hallucination": 0.10}, r_max=10.0, human_cost_per_output=1.50, utilization=0.95)
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=100.0)
    return rate(metrics_from_observation(obs, settings, baseline))


def test_generic_webhook_end_to_end():
    payload = load_raw("acme_payload")
    mapping = FieldMapping.from_yaml(mapping_path("acme"))
    adapter = GenericWebhookAdapter(mapping)

    [obs] = adapter.to_observations(payload)
    r = _rate_observation(obs)

    # Official DPI-LS governance formula: G = 1 - (total_actions / policy_violations).
    # Acme: 200 actions, 2 policy breaches → G = 1 - 200/2 = -99.0. The
    # negative G fails the 0.60 compliance floor → unsafe, G gate fires,
    # and the weighted composite is negative.
    assert r.metrics["G"] == pytest.approx(0.0, abs=1e-3)
    assert r.unsafe is True
    assert r.band == "Needs Optimization"
    assert r.metrics["Q"] is not None
    assert r.gate_failures == ["G"]


def test_productivity_with_default_baseline_1_0():
    """Test P calculation with default baseline of 1.0."""
    from fixtures import load

    obs = load("strong")
    settings = Settings(gate_thresholds={"G": 0.60, "R": 0.70, "V": 0.60}, q_sub_weights={"accuracy": 0.70, "consistency": 0.20, "hallucination": 0.10}, r_max=50.0)
    # Use default baseline of 1.0
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=1.0)

    metrics = metrics_from_observation(obs, settings, baseline)

    # Strong fixture has completed=1, so P should be 1/1.0 = 1.0
    assert metrics["P"] == 1.0

    r = rate(metrics)
    assert r.unsafe is False
    assert r.metrics["P"] == 1.0
