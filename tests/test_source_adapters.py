from __future__ import annotations

import pytest

from contract import PartialObservation
from fixtures import load_source
from ingestion.sources import (
    ArizeAdapter,
    AwsCostAdapter,
    JiraAdapter,
    PuviNoiseAdapter,
    ServiceNowAdapter,
)
from ingestion.sources.stubs import ALL_STUBS


def test_aws_cost_emits_cost_partial_only():
    [p] = AwsCostAdapter().to_partials(load_source("aws_cost"))
    assert p.agent_id == "agent-multi-001"
    assert p.cost is not None
    # The contract no longer carries ai_cost_per_output — the engine
    # derives it from model_cost / tasks.completed at scoring time.
    # The adapter forwards the spend total as model_cost and the
    # output_count as a tasks block so the math comes out to the
    # same per-output figure the old contract carried directly.
    assert p.cost.model_cost == pytest.approx(26.40)
    # Legacy "tokens" rollup is split 50/50 by the adapter when the
    # caller doesn't supply the in/out split explicitly.
    assert p.cost.input_tokens == 540000 // 2
    assert p.cost.output_tokens == 540000 - p.cost.input_tokens
    assert p.tasks is not None
    assert p.tasks.completed == 88
    # Other dimensions stay None — that's the whole point of a
    # cost-only source.
    assert p.policy is None
    assert p.incidents is None
    assert p.quality is None
    assert p.validation is None


def test_aws_cost_without_output_count_stays_strictly_cost_only():
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [{"agent_id": "a", "spend_usd": 5.0}],
    }
    [p] = AwsCostAdapter().to_partials(payload)
    # No output_count → no tasks block; the engine falls back to
    # treating the cost total as a single-output figure.
    assert p.cost.model_cost == 5.0
    assert p.tasks is None


def test_puvi_noise_emits_policy_partial():
    [p] = PuviNoiseAdapter().to_partials(load_source("puvi_noise"))
    assert p.policy is not None
    assert p.policy.total_actions == 200
    assert len(p.policy.violations) == 3
    assert p.policy.violations[0].rule == "pii.email_redaction"
    assert p.cost is None and p.quality is None and p.incidents is None


def test_arize_emits_policy_and_quality():
    [p] = ArizeAdapter().to_partials(load_source("arize"))
    assert p.policy is not None
    assert p.policy.total_actions == 1200
    assert len(p.policy.violations) == 1
    assert p.quality is not None
    assert p.quality.accuracy == 0.93


def test_arize_omits_quality_when_payload_omits():
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "agents": [{
            "agent_id": "a",
            "model_inferences": 100,
            "monitor_breaches": [],
        }],
    }
    [p] = ArizeAdapter().to_partials(payload)
    assert p.quality is None
    assert p.policy is not None


def test_servicenow_maps_impact_to_severity_and_groups_by_agent():
    partials = ServiceNowAdapter().to_partials(load_source("servicenow"))
    by_agent = {p.agent_id: p for p in partials}
    assert "agent-multi-001" in by_agent and "another-agent" in by_agent
    incidents = by_agent["agent-multi-001"].incidents
    assert len(incidents) == 2
    weights = sorted(i.severity_weight for i in incidents)
    assert weights == pytest.approx([0.3, 0.6])  # impact 3 → 0.3, impact 2 → 0.6


def test_servicenow_drops_tickets_without_agent_id():
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "tickets": [
            {"number": "INC001", "impact": 1, "opened_at": "2026-06-01T00:00:00Z"},
        ],
    }
    assert ServiceNowAdapter().to_partials(payload) == []


def test_jira_priority_maps_to_severity():
    [p] = JiraAdapter().to_partials(load_source("jira"))
    assert p.agent_id == "agent-multi-001"
    assert len(p.incidents) == 1
    assert p.incidents[0].severity_weight == 0.3  # "Low"


@pytest.mark.parametrize("cls", ALL_STUBS)
def test_stubs_register_and_return_empty(cls):
    adapter = cls()
    assert adapter.name
    assert adapter.to_partials({}) == []
