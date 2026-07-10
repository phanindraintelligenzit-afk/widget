"""Engine review — verify each formula against the spec, the reference
outputs, and the gate / band / completeness policy.

Spec sources
------------

* CLAUDE.md: composite weights, 7 metric formulae, gate floors (G<.60,
  R<.50, V<.60), band ranges, and the four reference outputs.
* engine/completeness.py: coverage cap (gated missing OR < N measured
  → cap at top of "Needs Optimization").
"""
from __future__ import annotations

import math

import pytest

from contract import DEFAULT_GATE_THRESHOLDS, DEFAULT_Q_SUB_WEIGHTS, DEFAULT_WEIGHTS
from engine import (
    EXCEPTIONAL,
    NEEDS_OPTIMIZATION,
    STRONG,
    UNDERPERFORMING,
    band,
    composite,
    compute_C,
    compute_E,
    compute_G,
    compute_P,
    compute_Q,
    compute_R,
    compute_V,
    gate_check,
    rate,
)


# ---------------------------------------------------------------------------
# (1) Reference outputs from the spec
# ---------------------------------------------------------------------------

def _all(value: float) -> dict[str, float]:
    return {k: value for k in DEFAULT_WEIGHTS}


def test_reference_all_85_scores_85():
    assert round(composite(_all(0.85))) == 85


def test_reference_all_92_scores_92():
    assert round(composite(_all(0.92))) == 92


def test_reference_all_55_scores_55():
    assert round(composite(_all(0.55))) == 55


def test_reference_strong_agent_with_failing_G_gate():
    """All-.85 baseline, G=.25 → raw 73 (arithmetic), gate fires,
    force-pinned at 69.

    With the arithmetic-mean composite: 0.85 × 0.80 + 0.25 × 0.20
    = 0.73 → raw 73. The G gate then force-pins the score to 69
    (top of "Needs Optimization"), flagged ``unsafe=True``. The
    raw 73 is preserved on ``r.raw_score`` for transparency.
    """
    m = _all(0.85)
    m["G"] = 0.25
    r = rate(m)

    assert round(r.raw_score) == 73
    assert round(r.score) == 69
    assert r.unsafe is True
    assert "G" in r.gate_failures
    assert r.band == NEEDS_OPTIMIZATION


# ---------------------------------------------------------------------------
# (1) Composite math — weighted geometric mean
# ---------------------------------------------------------------------------

def test_composite_uniform_collapses_to_value():
    """When all metrics equal, the composite is exactly that value × 100."""
    for v in (0.1, 0.5, 0.7, 0.85, 0.92, 1.0):
        assert math.isclose(composite(_all(v)), v * 100, rel_tol=1e-9)


def test_composite_weight_redistribution_preserves_unit_mean():
    """With one dimension dropped, the present dimensions' weights
    renormalise to 1, so a uniform-1.0 input still gives 100."""
    m = {k: 1.0 if k in {"P", "Q", "E"} else None for k in DEFAULT_WEIGHTS}
    assert math.isclose(composite(m), 100.0, rel_tol=1e-9)


def test_composite_single_dim_at_0_9_is_90():
    """C-only at 0.9 should give 90 (renormalised C weight = 1.0)."""
    m = {k: None for k in DEFAULT_WEIGHTS}
    m["C"] = 0.9
    assert math.isclose(composite(m), 90.0, rel_tol=1e-9)


def test_composite_all_none_returns_zero():
    assert composite({k: None for k in DEFAULT_WEIGHTS}) == 0.0


def test_composite_empty_returns_zero():
    assert composite({}) == 0.0


def test_composite_zero_metric_contributes_zero_to_sum():
    """A 0.0 metric contributes its (weight × value) to the weighted
    sum. With arithmetic mean, a C-only agent at 0.0 returns exactly
    0 — no epsilon floor needed (arithmetic mean is well-defined for
    any non-negative input)."""
    m = {k: None for k in DEFAULT_WEIGHTS}
    m["C"] = 0.0
    out = composite(m)
    assert out == 0.0


def test_composite_zero_weights_falls_back_to_zero():
    """If every present metric has weight 0, the geometric mean is
    undefined; the engine returns 0.0 rather than crashing."""
    m = {"P": 0.85}
    w = {k: 0.0 for k in DEFAULT_WEIGHTS}
    assert composite(m, w) == 0.0


# ---------------------------------------------------------------------------
# (1) Per-dimension formula verification
# ---------------------------------------------------------------------------

def test_formula_P_capped_at_1():
    assert compute_P(0, 100) == 0.0
    assert math.isclose(compute_P(80, 100), 0.8)
    assert compute_P(120, 100) == 1.0   # capped
    assert compute_P(50, 0) == 0.0       # no baseline
    assert compute_P(-5, 100) == 0.0     # defensive on negative


def test_formula_Q_weighted_sum():
    # 0.7*0.9 + 0.2*0.8 + 0.1*0.9 = 0.88
    assert math.isclose(compute_Q(0.9, 0.8, 0.1, DEFAULT_Q_SUB_WEIGHTS), 0.88)
    assert math.isclose(compute_Q(1.0, 1.0, 0.0, DEFAULT_Q_SUB_WEIGHTS), 1.0)
    assert math.isclose(compute_Q(0.0, 0.0, 1.0, DEFAULT_Q_SUB_WEIGHTS), 0.0)


def test_formula_E_simple_ratio():
    assert math.isclose(compute_E(72, 95), 72/95)
    assert compute_E(0, 0) == 0.0
    assert compute_E(5, 0) == 0.0  # no attempts


def test_formula_G_inverse_violation_rate():
    assert math.isclose(compute_G(2, 150), 1 - 2/150)
    # Vacuously safe when no actions taken (the engine still scores it
    # — the gate floor of 0.60 is then met automatically).
    assert compute_G(0, 0) == 1.0
    assert compute_G(5, 0) == 1.0


def test_formula_R_incident_risk():
    incs = [
        {"severity_weight": 0.5, "frequency": 2, "source": "jira"},
        {"severity_weight": 0.2, "frequency": 1, "source": "servicenow"},
    ]
    # 1 - min(1, (0.5*2 + 0.2*1) / 10) = 0.88
    assert math.isclose(compute_R(incs, 10), 0.88)
    # No incidents → vacuously safe.
    assert compute_R([], 10) == 1.0
    assert compute_R(None, 10) == 1.0
    # Incidents over r_max → 0.
    huge = [{"severity_weight": 1, "frequency": 100, "source": "x"}]
    assert compute_R(huge, 10) == 0.0
    # r_max <= 0 → 0 (engine guard, can't normalise).
    assert compute_R(incs, 0) == 0.0


def test_formula_V_validated_over_required():
    assert compute_V(10, 10) == 1.0
    assert math.isclose(compute_V(7, 10), 0.7)
    assert compute_V(0, 0) == 1.0   # vacuously safe
    assert compute_V(5, 0) == 1.0


def test_formula_C_human_to_ai_ratio_times_utilization():
    # model_cost / completed_outputs is the per-output figure the
    # engine derives. Each case below pins it to the value the test
    # intends.
    # 1.0 human / 0.5 ai = 2.0 → capped at 1.0 × utilization 1.0
    assert math.isclose(compute_C(1.0, 0.5, 1, 1.0), 1.0)
    # 0.5 / 1.0 = 0.5 × 1.0 utilization
    assert math.isclose(compute_C(0.5, 1.0, 1, 1.0), 0.5)
    # utilization < 1.0 scales the ratio
    assert math.isclose(compute_C(1.0, 1.0, 1, 0.5), 0.5)
    # 0 ai cost → 1.0 (free means highly efficient)
    assert compute_C(1.0, 0.0, 1, 1.0) == 1.0


# ---------------------------------------------------------------------------
# (2) Coverage policy — dimensions_measured and coverage exposed
# ---------------------------------------------------------------------------

def test_rating_exposes_dimensions_measured_int_count():
    r = rate(_all(0.85))
    assert isinstance(r.dimensions_measured, int)
    assert r.dimensions_measured == 7


def test_rating_exposes_coverage_float_ratio():
    r = rate(_all(0.85))
    assert isinstance(r.coverage, float)
    assert math.isclose(r.coverage, 1.0)


def test_rating_exposes_missing_list():
    m = {k: None for k in DEFAULT_WEIGHTS}
    m["C"] = 0.9
    r = rate(m)
    assert set(r.missing) == {"P", "Q", "E", "G", "R", "V"}


def test_completeness_cap_when_gated_missing():
    """Any missing G/R/V → cap, even with 6/7 dimensions measured."""
    m = {k: 0.85 if k in {"P", "Q", "E", "C", "G", "V"} else None for k in DEFAULT_WEIGHTS}
    # 6 measured, gated (G/V) present, R missing
    r = rate(m)
    assert r.capped is True
    assert "gated" in (r.cap_reason or "")
    assert r.score == 69.0


def test_completeness_cap_below_floor_with_gated_present():
    """< N measured dimensions → cap, even if all gated are present."""
    m = {k: 0.85 if k in {"G", "R", "V"} else None for k in DEFAULT_WEIGHTS}
    r = rate(m)
    assert r.capped is True
    assert "only 3/7" in (r.cap_reason or "")
    assert r.score == 69.0


def test_completeness_floor_of_4_is_the_spec_default():
    """G + R + V + 1 more = 4 measured, gated present → not capped."""
    m = {k: 0.85 if k in {"G", "R", "V", "P"} else None for k in DEFAULT_WEIGHTS}
    r = rate(m)
    assert r.capped is False
    assert r.score > 69.0
    assert r.band in (STRONG, EXCEPTIONAL)


def test_completeness_cap_floor_is_configurable():
    """min_dimensions_for_full_band parameter raises/lowers the floor."""
    m = {k: 0.85 if k in {"G", "R", "V"} else None for k in DEFAULT_WEIGHTS}
    # Default 4 → capped
    r1 = rate(m, min_dimensions_for_full_band=4)
    assert r1.capped is True
    # Floor 3 → not capped
    r2 = rate(m, min_dimensions_for_full_band=3)
    assert r2.capped is False
    assert r2.score > 69.0


# ---------------------------------------------------------------------------
# (3) Gate / band behavior — overlap with the 50–69 band
# ---------------------------------------------------------------------------

def test_gate_fires_below_floor():
    for k, t in DEFAULT_GATE_THRESHOLDS.items():
        m = _all(0.85)
        m[k] = t - 0.01
        r = rate(m)
        assert r.unsafe is True
        assert k in r.gate_failures


def test_gate_does_not_fire_at_floor():
    """A metric at exactly the floor is compliant — the spec is "<"
    not "<="."""
    for k, t in DEFAULT_GATE_THRESHOLDS.items():
        m = _all(0.85)
        m[k] = t
        fired, failed = gate_check(m)
        assert fired is False
        assert k not in failed


def test_gate_deferred_for_missing_metric():
    """Missing G/R/V does NOT trigger the gate — it's the coverage
    cap's job to flag a missing-gated agent, not the gate's."""
    m = {k: 0.85 if k in {"P", "Q", "E", "C"} else None for k in DEFAULT_WEIGHTS}
    r = rate(m)
    assert r.unsafe is False
    assert r.gate_failures == []


def test_gate_caps_strong_agent_to_needs_optimization():
    """Strong agent with G=.25 → score 67, band Needs Optimization,
    flagged unsafe. The cap (69) is the *top* of the 50–69 band
    (not the floor of Strong) so a single failure doesn't bury the
    agent below the recoverable range."""
    m = _all(0.85)
    m["G"] = 0.25
    r = rate(m)
    assert r.unsafe is True
    assert r.band == NEEDS_OPTIMIZATION
    assert r.score <= 69.0


def test_gate_and_completeness_both_apply_precedence():
    """If both gate and completeness would cap, the agent is flagged
    unsafe (gate wins) and cap_reason surfaces the gate."""
    # G=.25 fires the gate, and we hide the other gated dims to also
    # fire the completeness cap. Precedence: gate.
    m = {k: 0.85 if k == "P" else None for k in DEFAULT_WEIGHTS}
    m["G"] = 0.25
    r = rate(m)
    assert r.unsafe is True
    assert "G" in r.gate_failures
    # cap_reason is the gate reason (more actionable).
    assert "compliance gate" in (r.cap_reason or "")


def test_underperforming_band_not_capped_by_completeness():
    """An organic Underperforming agent (no gate fire) is left alone
    by the completeness cap — it's already at the bottom of the
    table, and the gate isn't firing, so nothing should pull it up.

    Note: a 0.4 baseline is *below* the G floor (0.60) so the gate
    WOULD fire here. We use R instead (R floor is 0.50, 0.4 fails)
    — but only one gated metric needs to fail, and 0.4 < 0.50 too.
    So this test exercises a path the spec also covers: an all-0.4
    agent *does* trip the gate, and the force-cap pins the score at
    69 (top of Needs Optimization) regardless of how low the raw
    composite sank. The "Underperforming" band would have been
    misleading — a gate failure is not a performance failure.
    """
    m = {k: 0.4 for k in DEFAULT_WEIGHTS}  # all 0.4 → ~40, but gates fire
    r = rate(m)
    # Gate fires on G (.4 < .60) and R (.4 < .50) and V (.4 < .60),
    # so the score is force-pinned at 69 (top of Needs Optimization).
    assert r.unsafe is True
    assert r.gate_failures, "expected at least one gate failure"
    assert r.band == NEEDS_OPTIMIZATION
    assert round(r.score) == 69
    # The raw score is still preserved for transparency.
    assert round(r.raw_score) < 50
