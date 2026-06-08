"""M2 demand: push a fixture through to a computed score end-to-end.

Two paths exercised: GenericWebhookAdapter (YAML) and OTelAdapter.
Both flow: raw payload -> adapter -> AgentObservation -> engine -> Rating.
The engine never sees the adapter; the adapter never sees the engine.
"""
from __future__ import annotations

from contract import AgentBaseline, Settings
from engine import metrics_from_observation, rate
from ingestion import FieldMapping, GenericWebhookAdapter, OTelAdapter
from fixtures import load_otel_spans, load_raw, mapping_path


def _rate_observation(obs):
    settings = Settings(r_max=10.0, human_cost_per_output=1.50, utilization=0.95)
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=100.0)
    return rate(metrics_from_observation(obs, settings, baseline))


def test_generic_webhook_end_to_end():
    payload = load_raw("acme_payload")
    mapping = FieldMapping.from_yaml(mapping_path("acme"))
    adapter = GenericWebhookAdapter(mapping)

    [obs] = adapter.to_observations(payload)
    r = _rate_observation(obs)

    assert r.unsafe is False
    assert r.band in ("Strong", "Exceptional")
    assert 70 <= r.score <= 100
    assert r.metrics["Q"] is not None
    assert r.gate_failures == []


def test_otel_end_to_end():
    spans = load_otel_spans()
    [obs] = OTelAdapter().to_observations(spans)

    settings = Settings()
    # The OTel fixture has 3 task spans → use a per-agent baseline that
    # matches the span volume rather than the 100/period default.
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=3.0)
    r = rate(metrics_from_observation(obs, settings, baseline))

    # 1 violation / 4 actions = G of 0.75 → above gate threshold → safe.
    assert r.unsafe is False
    assert r.metrics["G"] == 0.75
    assert r.gate_failures == []
    assert 0 < r.score <= 100


def test_productivity_with_default_baseline_1_0():
    """Test P calculation with default baseline of 1.0."""
    from fixtures import load

    obs = load("strong")
    settings = Settings()
    # Use default baseline of 1.0
    baseline = AgentBaseline(agent_id=obs.agent_id, human_output_per_period=1.0)

    metrics = metrics_from_observation(obs, settings, baseline)

    # Strong fixture has completed=1, so P should be 1/1.0 = 1.0
    assert metrics["P"] == 1.0

    r = rate(metrics)
    assert r.unsafe is False
    assert r.metrics["P"] == 1.0
