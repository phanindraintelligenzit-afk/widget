from __future__ import annotations

from datetime import datetime, timezone

import pytest

from contract import (
    AgentBaseline,
    Cost,
    PartialObservation,
    Policy,
    PolicyViolation,
    Quality,
    Settings,
    TaskStats,
    merge_partials,
)
from engine import metrics_from_partial, rate


def _p(source, **fields):
    return PartialObservation(
        agent_id="a",
        period_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 6, 2, tzinfo=timezone.utc),
        source=source,
        **fields,
    )


def test_merge_takes_latest_per_dimension():
    early = _p("puvi", policy=Policy(total_actions=100, violations=[]))
    late = _p("puvi", policy=Policy(total_actions=100, violations=[
        PolicyViolation(rule="x", when=datetime(2026, 6, 1, 12, tzinfo=timezone.utc)),
    ]))
    merged = merge_partials([early, late])
    assert len(merged.policy.violations) == 1


def test_merge_keeps_dimensions_from_separate_sources():
    cost = _p("aws_cost", cost=Cost(ai_cost_per_output=0.30))
    pol = _p("puvi", policy=Policy(total_actions=50, violations=[]))
    qua = _p("arize", quality=Quality(accuracy=0.9, consistency=0.85, hallucination_rate=0.05))
    merged = merge_partials([cost, pol, qua])
    assert merged.cost.ai_cost_per_output == 0.30
    assert merged.policy.total_actions == 50
    assert merged.quality.accuracy == 0.9
    # Dimensions nobody contributed stay None.
    assert merged.tasks is None
    assert merged.incidents is None
    assert merged.validation is None
    assert merged.executions is None


def test_metrics_from_partial_returns_None_for_missing_dimensions():
    p = _p("aws_cost", cost=Cost(ai_cost_per_output=1.0))
    settings = Settings(human_cost_per_output=1.0, utilization=1.0)
    baseline = AgentBaseline(agent_id="a", human_output_per_period=100)
    m = metrics_from_partial(p, settings, baseline)
    assert m["C"] == 1.0
    for k in ("P", "Q", "E", "G", "R", "V"):
        assert m[k] is None


def test_rate_redistributes_weight_for_present_metrics_only():
    """A C-only observation redistributes weight to C, but gets capped due to completeness."""
    p = _p("aws_cost", cost=Cost(ai_cost_per_output=1.0))
    settings = Settings(human_cost_per_output=1.0, utilization=1.0)
    baseline = AgentBaseline(agent_id="a", human_output_per_period=100)
    r = rate(metrics_from_partial(p, settings, baseline))

    # Raw score would be 100.0 (perfect C redistributed), but gets capped
    assert r.raw_score == pytest.approx(100.0)  # Weight redistribution works
    assert r.score == 69.0  # Capped to top of "Needs Optimization"
    assert r.capped is True  # Completeness cap applied
    assert "low-coverage" in r.cap_reason  # Reason is low coverage
    assert set(r.missing) == {"P", "Q", "E", "G", "R", "V"}


def test_merge_empty_raises():
    with pytest.raises(ValueError):
        merge_partials([])
