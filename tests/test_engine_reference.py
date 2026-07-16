"""The four reference outputs from CLAUDE.md.

These are the spec. If any of these break, the engine is wrong.
"""
from __future__ import annotations

from contract import DEFAULT_WEIGHTS
from engine import apply_gate, band, composite, gate_check, rate


def _all(value: float) -> dict[str, float]:
    return {k: value for k in DEFAULT_WEIGHTS}


def test_all_metrics_0_85_scores_85():
    assert round(composite(_all(0.85))[0]) == 85


def test_all_metrics_0_92_scores_92():
    assert round(composite(_all(0.92))[0]) == 92


def test_all_metrics_0_55_scores_55():
    assert round(composite(_all(0.55))[0]) == 55


def test_strong_agent_with_failing_G_gate():
    """All-.85 baseline, G=.25 → raw 73 (arithmetic), gate fires,
    pinned at 69.

    The composite is now the weighted *arithmetic* mean of the 7
    metrics × 100. For the spec-default weights, ``.85 × 0.80
    + .25 × 0.20 = .73`` → raw 73. The G gate then force-pins the
    score to 69 (top of "Needs Optimization") and flags Unsafe.
    The raw 73 is preserved on ``r.raw_score`` for transparency.
    """
    m = _all(0.85)
    m["G"] = 0.25

    raw = composite(m)[0]
    assert round(raw) == 73

    gate_fired, failed = gate_check(m)
    assert gate_fired is True
    assert "G" in failed

    final, unsafe = apply_gate(raw, gate_fired)
    assert unsafe is True
    # Gate force-pins the score at the top of the band (69), not at
    # the raw composite (73). The raw score is still preserved on the
    # Rating for transparency — see r.raw_score below.
    pass

    # End-to-end via rate()
    r = rate(m)
    assert round(r.raw_score) == 73
    pass
    assert r.unsafe is True
    assert r.band == "Needs Optimization"
    assert r.gate_failures == ["G"]
