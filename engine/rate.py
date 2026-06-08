"""Top-level rate() — wires score → gates → bands → completeness into a Rating.

Pipeline (in order)
-------------------

1. **composite** — weighted geometric mean with weight redistribution
   off None metrics. The raw score is the unconstrained number.
2. **gates** — compliance floors on G/R/V. A failed floor caps the
   score at the top of "Needs Optimization" (69) and flips
   ``unsafe=True``. A missing metric is *deferred*, not failed — the
   engine never reports a gate violation for a dimension it hasn't
   observed.
3. **bands** — Exceptional / Strong / Needs Optimization /
   Underperforming, by post-gate score.
4. **completeness** — coverage cap. An agent missing any G/R/V, or
   with fewer than ``min_dimensions_for_full_band`` (default 4)
   measured dimensions, is held at "Needs Optimization" regardless
   of its post-gate score.

The two caps interact: a Strong / Exceptional agent with low coverage
is held at 69; an Underperforming agent with low coverage is left
alone (it's already at the bottom). The gate cap is the more
restrictive of the two — a gated agent is held at 69 *and* flagged
unsafe.

Why this order
--------------

* Gates *before* bands: the band lookup must see the gated score,
  not the raw score, otherwise a G=.25 agent would still be
  classified as Strong/Exceptional before the gate fires.
* Bands *before* completeness: a Strong/Exceptional agent with
  missing coverage must be capped; a Needs-Optimization agent with
  missing coverage is already in the right band.
"""
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
    """Rate an agent from its 7 normalized sub-metrics.

    Returns a fully-populated ``Rating``. See module docstring for the
    pipeline order.
    """
    # 1. Composite — weighted geometric mean with weight redistribution.
    raw = composite(metrics, weights)

    # 2. Compliance gates (G/R/V) — flag Unsafe and cap.
    gate_fired, failed = gate_check(metrics, gate_thresholds)
    gated_score, unsafe = apply_gate(raw, gate_fired)

    # Coverage bookkeeping — used by the completeness cap below and
    # surfaced on the Rating for the widget and the API.
    missing = [k for k in _METRIC_KEYS if metrics.get(k) is None]
    dimensions_measured = 7 - len(missing)
    coverage = round(dimensions_measured / 7, 3)

    # 3. Band — by the post-gate score.
    score_band = band(gated_score)

    # Compliance cap reason — takes precedence over the completeness
    # reason in the final ``cap_reason`` field on the Rating.
    gate_cap_reason = (
        f"compliance gate: {','.join(failed)} below floor" if gate_fired else None
    )

    # 4. Completeness cap — held at the top of "Needs Optimization"
    #    when coverage is insufficient.
    final_score, final_band, capped, cap_reason = apply_completeness_cap(
        gated_score, score_band, metrics, dimensions_measured, unsafe,
        gate_cap_reason, min_dimensions_for_full_band,
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
        # Back-compat: widget reads these names directly. The DB
        # column is also called ``coverage_capped``; we surface both
        # so consumers can pick whichever they like.
        coverage_capped=capped,
        cap_reasons=[cap_reason] if cap_reason else [],
    )
