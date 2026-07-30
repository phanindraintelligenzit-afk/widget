from __future__ import annotations

import pytest

from contract import PartialObservation
from fixtures import load_source
from ingestion.sources import (
    AwsCostAdapter,
    JiraAdapter,
    PuviNoiseAdapter,
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


def test_jira_priority_maps_to_severity():
    [p] = JiraAdapter().to_partials(load_source("jira"))
    assert p.agent_id == "agent-multi-001"
    assert len(p.incidents) == 1
    assert p.incidents[0].severity_weight == 0.3  # "Low"



