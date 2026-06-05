"""Test completeness capping logic."""
from __future__ import annotations

from contract import DEFAULT_WEIGHTS
from engine import rate


def _metrics(**kwargs) -> dict[str, float | None]:
    """Build a metrics dict with specified values, others None."""
    base = {k: None for k in DEFAULT_WEIGHTS}
    base.update(kwargs)
    return base


def test_only_cost_agent_gets_capped():
    """Only-Cost agent (G,R,V,P,Q,E missing), C high: capped to Needs Optimization."""
    metrics = _metrics(C=0.9)  # Only Cost measured, high value

    r = rate(metrics)

    assert r.dimensions_measured == 1
    assert r.coverage == round(1/7, 3)  # 0.143
    assert r.band == "Needs Optimization"
    assert r.capped is True
    assert "low-coverage" in r.cap_reason


def test_four_measured_but_gated_missing_gets_capped():
    """Agent with P,Q,E,C measured high but G,R,V missing: capped (gated dims absent)."""
    metrics = _metrics(P=0.85, Q=0.85, E=0.85, C=0.85)  # 4 measured but no gated ones

    r = rate(metrics)

    assert r.dimensions_measured == 4
    assert r.coverage == round(4/7, 3)
    assert r.band == "Needs Optimization"  # Would be Strong without cap
    assert r.capped is True
    assert "gated dimensions missing" in r.cap_reason


def test_gated_plus_one_not_capped():
    """Agent with G,R,V + one more, all .85: not capped."""
    metrics = _metrics(G=0.85, R=0.85, V=0.85, P=0.85)  # All gated + 1 more = 4 total

    r = rate(metrics)

    assert r.dimensions_measured == 4
    assert r.coverage == round(4/7, 3)
    assert r.band == "Exceptional"  # 85 score, no cap
    assert r.capped is False
    assert r.cap_reason is None


def test_min_dimensions_setting_affects_cap():
    """Test that changing min_dimensions_for_full_band affects capping behavior."""
    # Agent with exactly 3 dimensions measured including gated ones, all high
    metrics = _metrics(G=0.85, R=0.85, V=0.85)  # 3 measured, all gated (so gated requirement met)

    # With default (4): should be capped due to insufficient total dimensions
    r1 = rate(metrics, min_dimensions_for_full_band=4)
    assert r1.dimensions_measured == 3
    assert r1.capped is True
    assert "low-coverage (only 3/7 dimensions)" in r1.cap_reason
    assert r1.band == "Needs Optimization"

    # With setting changed to 3: should NOT be capped (meets both gated and total requirements)
    r2 = rate(metrics, min_dimensions_for_full_band=3)
    assert r2.dimensions_measured == 3
    assert r2.capped is False
    assert r2.cap_reason is None
    assert r2.band == "Exceptional"  # High scores, not capped

    # With setting changed to 2: should NOT be capped
    r3 = rate(metrics, min_dimensions_for_full_band=2)
    assert r3.dimensions_measured == 3
    assert r3.capped is False
    assert r3.cap_reason is None
    assert r3.band == "Exceptional"


def test_reference_outputs_unchanged():
    """Re-assert the 4 reference outputs from CLAUDE.md are unchanged."""
    def _all(value: float) -> dict[str, float]:
        return {k: value for k in DEFAULT_WEIGHTS}

    # All metrics 0.85 → 85
    r1 = rate(_all(0.85))
    assert round(r1.score) == 85
    assert r1.band == "Exceptional"
    assert r1.capped is False

    # All metrics 0.92 → 92
    r2 = rate(_all(0.92))
    assert round(r2.score) == 92
    assert r2.band == "Exceptional"
    assert r2.capped is False

    # All metrics 0.55 → 55
    r3 = rate(_all(0.55))
    assert round(r3.score) == 55
    assert r3.band == "Needs Optimization"
    assert r3.capped is False

    # Strong agent but G=.25 → raw 67, gate fires, flagged Unsafe
    m4 = _all(0.85)
    m4["G"] = 0.25
    r4 = rate(m4)
    assert round(r4.raw_score) == 67
    assert round(r4.score) == 67
    assert r4.unsafe is True
    assert r4.band == "Needs Optimization"
    assert "G" in r4.gate_failures
    # Compliance gate takes precedence over completeness
    assert "compliance gate" in r4.cap_reason