"""Completeness caps — prevent inflated ratings from incomplete data.

A rating may exceed band "Needs Optimization" ONLY IF:
  (a) all of G, R, V are present (the gated dimensions), AND
  (b) ``dimensions_measured >= min_dimensions_for_full_band`` (default 4)

If either fails → cap band to "Needs Optimization", capped=True.
This is independent of compliance gates and applied after them.

Why this exists
---------------

The composite is a **weighted geometric mean** that *redistributes*
weight off any metric with value ``None``. This is the right thing
for sparse data: a C-only agent that reports ``C=1.0`` shouldn't be
penalised with a low score — it should get a high *raw* score that
makes it clear the agent is rated only on cost. But the raw score
shouldn't translate into a "Strong" or "Exceptional" band either,
because we genuinely don't know what the agent looks like on the
other 6 dimensions.

Policy
------

The default ``min_dimensions_for_full_band = 4`` is the spec's
"minimum viable" agent:

* G, R, V are the 3 *gated* (safety) dimensions — must all be present.
* At least 1 of P, Q, E, C is also required, for a minimum of 4.
* An agent missing any of G/R/V is capped regardless of how many
  other dimensions it reports (a 6-of-7 agent missing G is still
  unsafe to score above "Needs Optimization").

The value is configurable per-deployment via
``Settings.min_dimensions_for_full_band`` and the API persists it via
``PUT /settings``.

Precedence (final → most specific)
----------------------------------

* Compliance gate (G/R/V below floor) — flagged ``unsafe=True``.
* Coverage cap (gated missing OR < N dimensions) — flagged ``capped=True``.
* Both can apply; the gate is the most serious (it is the only path
  to ``unsafe=True``). The ``cap_reason`` surfaces the most relevant
  explanation; if both fired, the gate reason wins because it is
  the actionable signal.
"""
from __future__ import annotations

from typing import Optional

from .bands import NEEDS_OPTIMIZATION

# Gated dimensions — must all be present to exceed "Needs Optimization".
# These are the safety/quality dimensions and the spec's hard floors
# for the compliance gate. Mirrored in ``engine.gates.GATED_METRICS``
# for the gate-firing policy; this constant owns the coverage policy.
GATED: frozenset[str] = frozenset({"G", "R", "V"})

# Default floor on the number of measured dimensions required to break
# out of "Needs Optimization". Held here as the canonical default;
# configurable via :class:`contract.Settings`.
DEFAULT_MIN_DIMENSIONS: int = 4


def completeness_check(
    metrics: dict[str, Optional[float]],
    dimensions_measured: int,
    min_dimensions_for_full_band: int = DEFAULT_MIN_DIMENSIONS,
) -> tuple[bool, str | None]:
    """Return (should_cap, cap_reason).

    A rating may exceed "Needs Optimization" only if:
    1. All gated dimensions (G, R, V) are present, AND
    2. At least ``min_dimensions_for_full_band`` dimensions are
       measured total.
    """
    # Check if any gated dimensions are missing — this is a strict
    # requirement. A 6-of-7 agent missing G is still capped.
    missing_gated = [k for k in GATED if metrics.get(k) is None]
    if missing_gated:
        return True, "low-coverage (gated dimensions missing)"

    # Coverage floor on total dimensions measured.
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
    min_dimensions_for_full_band: int = DEFAULT_MIN_DIMENSIONS,
) -> tuple[float, str, bool, str | None]:
    """Apply completeness cap if needed.

    Returns (final_score, final_band, capped, final_cap_reason).
    Compliance gate caps take precedence over completeness caps.
    """
    should_cap, completeness_reason = completeness_check(
        metrics, dimensions_measured, min_dimensions_for_full_band
    )

    if not should_cap:
        return score, band, False, cap_reason

    # Only cap if the band would exceed "Needs Optimization". A
    # currently-Underperforming agent already lives at the bottom of
    # the table; the cap is a no-op for it.
    if band in ["Strong", "Exceptional"]:
        # Top of the "Needs Optimization" band. Holding the cap here
        # (not lower) keeps the agent in a recoverable position — a
        # single source coming online can lift it back above 70.
        capped_score = 69.0
        capped_band = NEEDS_OPTIMIZATION

        # If the gate already produced a reason, surface that — it's
        # the more actionable signal.
        final_cap_reason = cap_reason or completeness_reason

        return capped_score, capped_band, True, final_cap_reason

    # Band is already "Needs Optimization" or below — no-op.
    return score, band, False, cap_reason
