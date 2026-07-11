"""Component tests for individual metric helpers, gates, and bands.

These don't replace the reference tests — they cover edge cases the
spec leaves implicit.
"""
from __future__ import annotations

import pytest

from contract import DEFAULT_Q_SUB_WEIGHTS
from engine import (
    apply_gate,
    band,
    compute_C,
    compute_E,
    compute_G,
    compute_P,
    compute_Q,
    compute_R,
    compute_V,
    gate_check,
)
from engine.gates import NEEDS_OPT_CAP


# ---- bands ---------------------------------------------------------------

@pytest.mark.parametrize(
    "score,expected",
    [
        (100, "Exceptional"),
        (85,  "Exceptional"),
        (84.9, "Strong"),
        (70,  "Strong"),
        (69.9, "Needs Optimization"),
        (50,  "Needs Optimization"),
        (49.9, "Underperforming"),
        (0,   "Underperforming"),
    ],
)
def test_band_boundaries(score, expected):
    assert band(score) == expected


# ---- gates ---------------------------------------------------------------

def test_gate_passes_when_all_above_threshold():
    fired, failed = gate_check({"P": 1, "Q": 1, "E": 1, "G": 0.9, "R": 0.9, "V": 0.9, "C": 1})
    assert fired is False
    assert failed == []


def test_gate_caps_high_score():
    final, unsafe = apply_gate(95.0, True)
    assert unsafe is True
    assert final == NEEDS_OPT_CAP


def test_gate_force_pins_low_score_to_band_top():
    """When a gate fires, the score is force-pinned to the top of
    "Needs Optimization" (69) — even when the raw composite sank
    below the band (e.g. a 0 in one dim nuked the geometric mean).
    The gate is a force-cap, not a ceiling: it expresses a safety
    floor failure, not a performance failure.
    """
    final, unsafe = apply_gate(42.0, True)
    assert unsafe is True
    assert final == NEEDS_OPT_CAP  # 42.0 → pinned at 69


def test_gate_does_not_cap_when_no_fire():
    final, unsafe = apply_gate(42.0, False)
    assert unsafe is False
    assert final == 42.0


def test_gate_defers_when_metric_missing():
    # Missing Q should not trip the G/R/V gates.
    fired, failed = gate_check({"P": 1, "Q": None, "E": 1, "G": 0.9, "R": 0.9, "V": 0.9, "C": 1})
    assert fired is False
    assert failed == []


def test_gate_fires_on_R_and_V():
    fired, failed = gate_check({"P": 1, "Q": 1, "E": 1, "G": 1, "R": 0.4, "V": 0.5, "C": 1})
    assert fired is True
    assert set(failed) == {"R", "V"}


# ---- individual metric formulas -----------------------------------------

def test_P_caps_at_one():
    assert compute_P(200, 100) == 1.0


def test_P_zero_baseline_defends_against_div_zero():
    assert compute_P(50, 0) == 0.0


def test_P_with_baseline_1_0():
    """P should work correctly with default baseline of 1.0."""
    assert compute_P(1, 1.0) == 1.0  # AI matches human baseline exactly
    assert compute_P(0.5, 1.0) == 0.5  # AI is half as productive
    assert compute_P(2.0, 1.0) == 1.0  # AI exceeds baseline, capped at 1.0


def test_Q_uses_sub_weights():
    # 0.7*1 + 0.2*1 + 0.1*(1-0) = 1.0
    assert compute_Q(1.0, 1.0, 0.0, DEFAULT_Q_SUB_WEIGHTS) == pytest.approx(1.0)
    # 0.7*0.8 + 0.2*0.7 + 0.1*(1-0.1) = 0.56 + 0.14 + 0.09 = 0.79
    assert compute_Q(0.8, 0.7, 0.1, DEFAULT_Q_SUB_WEIGHTS) == pytest.approx(0.79)


def test_E_ratio():
    assert compute_E(80, 100) == 0.8
    assert compute_E(0, 0) == 0.0


def test_G_no_actions_is_compliant():
    assert compute_G(0, 0) == 1.0


def test_G_violation_ratio():
    assert compute_G(2, 10) == 0.8


def test_R_floors_at_zero():
    incidents = [{"severity_weight": 1.0, "frequency": 100, "source": "x"}]
    # total far exceeds r_max → clamped, R = 0
    assert compute_R(incidents, 10) == 0.0


def test_R_empty():
    assert compute_R([], 10) == 1.0


def test_V_proportional():
    assert compute_V(7, 10) == 0.7
    assert compute_V(0, 0) == 1.0


def test_C_includes_utilization():
    # human=2, model_cost=1, completed=1 → per-output=1 → ratio capped at 1
    # × utilization 0.5 = 0.5
    assert compute_C(2.0, 1.0, 1, 0.5) == 0.5
    # human=1, model_cost=2, completed=1 → per-output=2 → ratio 0.5
    # × utilization 1.0 = 0.5
    assert compute_C(1.0, 2.0, 1, 1.0) == 0.5
