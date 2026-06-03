from __future__ import annotations

from ingestion import OTelAdapter
from fixtures import load_otel_spans


def test_otel_fixture_round_trip():
    spans = load_otel_spans()
    obs_list = OTelAdapter().to_observations(spans)
    assert len(obs_list) == 1
    obs = obs_list[0]

    assert obs.agent_id == "otel-agent-007"
    assert obs.agent_name == "OTel Demo Agent"
    # 3 task spans → 2 OK + 1 ERROR
    assert obs.tasks.assigned == 3
    assert obs.tasks.completed == 2
    assert obs.tasks.failed == 1
    # 4 spans have policy.action=true (3 tasks + 1 policy span)
    assert obs.policy.total_actions == 4
    # 1 span with policy.violation=true
    assert len(obs.policy.violations) == 1
    assert obs.policy.violations[0].rule == "pii.email_redaction"
    # 1 incident
    assert len(obs.incidents) == 1
    assert obs.incidents[0].severity_weight == 0.4
    # quality from the one span that carried it
    assert obs.quality is not None
    assert obs.quality.accuracy == 0.93
    # validation
    assert obs.validation.required_components == 10
    assert obs.validation.validated_components == 9
    # cost
    assert obs.cost.tokens == (1200 + 400 + 900 + 350)
    assert obs.cost.cloud_cost == 0.012 + 0.009 + 0.004
    assert obs.source == "otel"


def test_otel_empty_quality_is_none():
    span = {
        "start_time": "2026-06-01T00:00:00Z",
        "end_time":   "2026-06-01T00:00:01Z",
        "status": {"code": "OK"},
        "resource": {"agent.id": "x"},
        "attributes": {"gen_ai.task": True, "policy.action": True},
    }
    obs = OTelAdapter().to_observations([span])[0]
    assert obs.quality is None


def test_otel_groups_by_agent():
    spans = [
        {"start_time": "2026-06-01T00:00:00Z", "end_time": "2026-06-01T00:00:01Z",
         "status": {"code": "OK"}, "resource": {"agent.id": "A"},
         "attributes": {"gen_ai.task": True}},
        {"start_time": "2026-06-01T00:00:00Z", "end_time": "2026-06-01T00:00:01Z",
         "status": {"code": "OK"}, "resource": {"agent.id": "B"},
         "attributes": {"gen_ai.task": True}},
    ]
    obs_list = OTelAdapter().to_observations(spans)
    assert {o.agent_id for o in obs_list} == {"A", "B"}
