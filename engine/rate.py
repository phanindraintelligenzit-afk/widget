"""Top-level rate() — wires score → gates → bands into a Rating."""
from __future__ import annotations

from typing import Optional

from contract import Rating

from .bands import band
from .gates import apply_gate, gate_check
from .score import composite


def rate(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    gate_thresholds: dict[str, float] | None = None,
) -> Rating:
    raw = composite(metrics, weights)
    gate_fired, failed = gate_check(metrics, gate_thresholds)
    final, unsafe = apply_gate(raw, gate_fired)
    missing = [k for k, v in metrics.items() if v is None]
    return Rating(
        score=round(final, 2),
        raw_score=round(raw, 2),
        band=band(final),
        unsafe=unsafe,
        gate_failures=failed,
        metrics=metrics,
        missing=missing,
    )
