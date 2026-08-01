"""Top-level rate() — wires score → gates → bands → completeness into a Rating.

Pipeline (in order)
-------------------

1. **composite** — weighted arithmetic mean with weight redistribution
   off None metrics. The raw score is the unconstrained number and
   is preserved on ``Rating.raw_score`` for full traceability.
2. **gates** — compliance floors on G/R/V. A failed floor flips
   ``unsafe=True``. A missing metric is *deferred*, not failed — the
   engine never reports a gate violation for a dimension it hasn't
   observed.
3. **completeness** — coverage cap. An agent missing any G/R/V, or
   with fewer than ``min_dimensions_for_full_band`` (default 4)
   measured dimensions, is flagged ``capped=True``.
4. **band** — Exceptional / Strong / Needs Optimization /
   Underperforming, by the raw score. If ``unsafe`` OR ``capped``
   would otherwise present as Strong/Exceptional, the band is
   overridden to "Needs Optimization" — a name, not a number, so no
   hardcoded score value leaks into the Rating. The score itself is
   preserved.

Why band override, not score cap
--------------------------------

Older versions hardcoded a numeric cap (69, top of "Needs Optimization")
into apply_gate / apply_completeness_cap. That approach put a magic
number in the engine and made the score less traceable. The current
approach overrides only the *band* (a categorical label) when a gate
or coverage cap fires — the raw score stays exactly what the composite
produced. Consumers who want the honest number read ``raw_score``;
consumers who want the safety-adjusted band read ``band``.
"""
from __future__ import annotations

from typing import Optional

from contract import Rating

from .bands import EXCEPTIONAL, NEEDS_OPTIMIZATION, STRONG, band
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
    # 1. Composite — DPI-LS formula and linear weighted metrics.
    raw, weighted_metrics, weights_used = composite(metrics, weights)

    # 2. Compliance gates (G/R/V) — flag Unsafe. Score is preserved
    #    (categorical band override below, no hardcoded numeric cap).
    gate_fired, failed = gate_check(metrics, gate_thresholds)
    gated_score, unsafe = apply_gate(raw, gate_fired)

    # Coverage bookkeeping — used by the completeness cap below and
    # surfaced on the Rating for the widget and the API.
    missing = [k for k in _METRIC_KEYS if metrics.get(k) is None]
    dimensions_measured = 7 - len(missing)
    coverage = round(dimensions_measured / 7, 3)

    # 3. Band — by the (uncapped) score. Use display-rounded value to
    #    avoid floating-point misclassification at boundaries
    #    (all-.85 → 84.9999… loses Exceptional otherwise).
    score_band = band(round(gated_score, 2))

    # Compliance cap reason — takes precedence over the completeness
    # reason in the final ``cap_reason`` field on the Rating.
    gate_cap_reason = (
        f"compliance gate: {','.join(failed)} below floor" if gate_fired else None
    )

    # 4. Completeness cap — evaluates whether the band should be
    #    held at "Needs Optimization" due to insufficient coverage.
    final_score, _completeness_band, capped, cap_reason = apply_completeness_cap(
        gated_score, score_band, metrics, dimensions_measured, unsafe,
        gate_cap_reason, min_dimensions_for_full_band,
    )

    # Band override — a *categorical* cap, not a numeric one. Unsafe
    # agents are always held at "Needs Optimization" (a gate failure
    # is not a performance failure — it must not be masked as either
    # Strong/Exceptional or Underperforming). Coverage-capped Strong/
    # Exceptional agents likewise get held at NEEDS_OPTIMIZATION.
    if unsafe:
        final_band = NEEDS_OPTIMIZATION
    elif capped and score_band in (STRONG, EXCEPTIONAL):
        final_band = NEEDS_OPTIMIZATION
    else:
        final_band = score_band

    return Rating(
        score=round(final_score, 2),
        raw_score=round(raw, 2),
        band=final_band,
        unsafe=unsafe,
        gate_failures=failed,
        metrics=metrics,
        weighted_metrics=weighted_metrics,
        weights_used=weights_used,
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
