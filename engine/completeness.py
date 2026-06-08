"""Completeness caps — prevent inflated ratings from incomplete data.

A rating may exceed band "Needs Optimization" ONLY IF:
  (a) none of G, R, V are missing, AND
  (b) dimensions_measured >= 4

If either fails -> cap band to "Needs Optimization", capped=True.
This is independent of compliance gates and applied after them.
"""
from __future__ import annotations

from typing import Optional

from .bands import NEEDS_OPTIMIZATION

# Gated dimensions that must be present to exceed "Needs Optimization"
GATED = {"G", "R", "V"}


def completeness_check(
    metrics: dict[str, Optional[float]],
    dimensions_measured: int,
    min_dimensions_for_full_band: int = 4,
) -> tuple[bool, str | None]:
    """Return (should_cap, cap_reason).

    A rating may exceed "Needs Optimization" only if:
    1. All gated dimensions (G, R, V) are present
    2. At least 4 dimensions are measured total
    """
    # Check if any gated dimensions are missing
    missing_gated = [k for k in GATED if metrics.get(k) is None]
    if missing_gated:
        return True, "low-coverage (gated dimensions missing)"

    # Check minimum dimension count
    if dimensions_measured < min_dimensions_for_full_band:
        return True, f"low-coverage (only {dimensions_measured}/7 dimensions)"

    return False, None


def apply_completeness_cap(
    score: float,
    band: str,
    metrics: dict[str, Optional[float]],
    dimensions_measured: int,
    unsafe: bool,
    cap_reason: str | None,
    min_dimensions_for_full_band: int = 4,
) -> tuple[float, str, bool, str | None]:
    """Apply completeness cap if needed.

    Returns (final_score, final_band, capped, final_cap_reason).
    Compliance gate caps take precedence over completeness caps.
    """
    should_cap, completeness_reason = completeness_check(metrics, dimensions_measured, min_dimensions_for_full_band)

    if not should_cap:
        return score, band, False, cap_reason

    # Only cap if the band would exceed "Needs Optimization"
    if band in ["Strong", "Exceptional"]:
        # Get the score for "Needs Optimization" band (69.0)
        from .bands import band as get_band
        capped_score = 69.0  # Top of "Needs Optimization" band
        capped_band = NEEDS_OPTIMIZATION

        # If already capped by gate, keep the gate reason prioritized
        final_cap_reason = cap_reason or completeness_reason

        return capped_score, capped_band, True, final_cap_reason

    # Band is already "Needs Optimization" or below, no need to cap
    return score, band, False, cap_reason