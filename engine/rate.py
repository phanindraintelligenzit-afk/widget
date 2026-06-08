"""Top-level rate() — wires score → gates → bands → completeness into a Rating."""
from __future__ import annotations

from typing import Optional

from contract import Rating

from .bands import band
from .completeness import apply_completeness_cap
from .gates import apply_gate, gate_check
from .score import composite


# Canonical metric key order for stable serialization.
_METRIC_KEYS = ("P", "Q", "E", "G", "R", "V", "C")


def rate(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    gate_thresholds: dict[str, float] | None = None,
    min_dimensions_for_full_band: int = 4,
) -> Rating:
    # Apply order: composite -> gates -> bands -> completeness cap LAST
    raw = composite(metrics, weights)

    # Compliance gates (G/R/V) — flag Unsafe and cap.
    gate_fired, failed = gate_check(metrics, gate_thresholds)
    gated_score, unsafe = apply_gate(raw, gate_fired)

    # Calculate coverage metrics
    missing = [k for k in _METRIC_KEYS if metrics.get(k) is None]
    dimensions_measured = 7 - len(missing)
    coverage = round(dimensions_measured / 7, 3)

    # Determine band based on gated score
    score_band = band(gated_score)

    # Initial cap reason from gates
    gate_cap_reason = f"compliance gate: {','.join(failed)} below floor" if gate_fired else None

    # Apply completeness cap LAST (precedence: compliance gate outranks coverage cap)
    final_score, final_band, capped, cap_reason = apply_completeness_cap(
        gated_score, score_band, metrics, dimensions_measured, unsafe, gate_cap_reason, min_dimensions_for_full_band
    )

    return Rating(
        score=round(final_score, 2),
        raw_score=round(raw, 2),
        band=final_band,
        unsafe=unsafe,
        gate_failures=failed,
        metrics=metrics,
        missing=missing,
        dimensions_measured=dimensions_measured,
        coverage=coverage,
        capped=capped,
        cap_reason=cap_reason,
    )
