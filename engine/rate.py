"""Top-level rate() — wires score → gates → coverage → bands into a Rating."""
from __future__ import annotations

from typing import Optional

from contract import Rating

from .bands import band
from .gates import NEEDS_OPT_CAP, apply_gate, gate_check
from .score import composite


# Canonical metric key order for stable serialization.
_METRIC_KEYS = ("P", "Q", "E", "G", "R", "V", "C")


def rate(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
    gate_thresholds: dict[str, float] | None = None,
    min_dimensions_for_full_band: int | None = None,
) -> Rating:
    raw = composite(metrics, weights)

    # Compliance gates (G/R/V) — flag Unsafe and cap.
    gate_fired, failed = gate_check(metrics, gate_thresholds)
    final, unsafe = apply_gate(raw, gate_fired)

    # Coverage — count distinct dimensions actually observed.
    dimensions_measured = [k for k in _METRIC_KEYS if metrics.get(k) is not None]
    coverage = len(dimensions_measured)
    missing = [k for k in _METRIC_KEYS if metrics.get(k) is None]

    cap_reasons: list[str] = []
    if gate_fired:
        cap_reasons.append(f"compliance gate: {','.join(failed)} below floor")

    # Coverage cap — separate from the compliance Unsafe flag. The score is
    # honest math; the band gets pulled down so a 1-dimension agent can't
    # display as Exceptional.
    coverage_capped = False
    if min_dimensions_for_full_band is not None and coverage < min_dimensions_for_full_band:
        if final > NEEDS_OPT_CAP:
            final = NEEDS_OPT_CAP
        coverage_capped = True
        cap_reasons.append(
            f"coverage {coverage}/7 below floor {min_dimensions_for_full_band}"
        )

    return Rating(
        score=round(final, 2),
        raw_score=round(raw, 2),
        band=band(final),
        unsafe=unsafe,
        gate_failures=failed,
        metrics=metrics,
        missing=missing,
        dimensions_measured=dimensions_measured,
        coverage=coverage,
        coverage_capped=coverage_capped,
        cap_reasons=cap_reasons,
    )
