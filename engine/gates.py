"""Hard compliance gates.

If G < 0.60 OR R < 0.50 OR V < 0.60 the rating is capped at the top of
the 'Needs Optimization' band and flagged Unsafe — regardless of score.
"""
from __future__ import annotations

from typing import Optional

from contract import DEFAULT_GATE_THRESHOLDS

# Top of the "Needs Optimization" band (50–69). Capping here guarantees
# the band lookup can't return Strong/Exceptional when a gate fires.
NEEDS_OPT_CAP = 69.0


def gate_check(
    metrics: dict[str, Optional[float]],
    thresholds: dict[str, float] | None = None,
) -> tuple[bool, list[str]]:
    """Return (gate_fired, failed_metric_names)."""
    thresholds = thresholds or DEFAULT_GATE_THRESHOLDS
    failed: list[str] = []
    for k, t in thresholds.items():
        v = metrics.get(k)
        if v is None:
            # Missing pending conversational capture — defer, don't fail.
            continue
        if v < t:
            failed.append(k)
    return (len(failed) > 0, failed)


def apply_gate(raw_score: float, gate_fired: bool) -> tuple[float, bool]:
    """Cap score at NEEDS_OPT_CAP if a gate fires; return (final, unsafe)."""
    if not gate_fired:
        return raw_score, False
    return min(raw_score, NEEDS_OPT_CAP), True
