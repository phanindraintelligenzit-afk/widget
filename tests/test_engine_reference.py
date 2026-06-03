"""The four reference outputs from CLAUDE.md.

These are the spec. If any of these break, the engine is wrong.
"""
from __future__ import annotations

from contract import DEFAULT_WEIGHTS
from engine import apply_gate, band, composite, gate_check, rate


def _all(value: float) -> dict[str, float]:
    return {k: value for k in DEFAULT_WEIGHTS}


def test_all_metrics_0_85_scores_85():
    assert round(composite(_all(0.85))) == 85


def test_all_metrics_0_92_scores_92():
    assert round(composite(_all(0.92))) == 92


def test_all_metrics_0_55_scores_55():
    assert round(composite(_all(0.55))) == 55


def test_strong_agent_with_failing_G_gate():
    """All-.85 baseline, G=.25 → raw 67, gate fires, flagged Unsafe."""
    m = _all(0.85)
    m["G"] = 0.25

    raw = composite(m)
    assert round(raw) == 67

    gate_fired, failed = gate_check(m)
    assert gate_fired is True
    assert "G" in failed

    final, unsafe = apply_gate(raw, gate_fired)
    assert unsafe is True
    # 67 is already inside Needs Optimization → cap is a no-op here.
    assert round(final) == 67

    # End-to-end via rate()
    r = rate(m)
    assert round(r.raw_score) == 67
    assert round(r.score) == 67
    assert r.unsafe is True
    assert r.band == "Needs Optimization"
    assert r.gate_failures == ["G"]
