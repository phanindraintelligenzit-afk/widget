"""Composite score — weighted geometric mean of the 7 sub-metrics × 100.

One model. Not a weighted sum. Weights live in Settings.

The math
--------

::

    DPI-LS = 100 · ∏ m_i ^ w_i  with  Σ w_i = 1

For the spec defaults ``P=.15, Q=.20, E=.15, G=.20, R=.15, V=.10, C=.05``
(sum 1.0), an agent scoring .85 on every dimension gets
``100 · 0.85^1.0 = 85``. The four reference outputs (85, 92, 55, and
the 67-gated Strong agent) all collapse cleanly to ``m^Σw`` when the
metrics are uniform — and to ``m_a^(w_a/Σ) · m_b^(w_b/Σ) ...`` when
they aren't.

Weight redistribution
---------------------

Metrics with value ``None`` are skipped AND their weight is
redistributed proportionally across present metrics. This preserves
the unit-mean invariant when, for example, Q is missing pending
conversational capture. A C-only agent with ``C=0.9`` scores
``0.9^(0.05/0.05) · 100 = 90`` — the right answer for the C slice
but obviously not "Strong". The completeness cap (see
``engine.completeness``) is what keeps that 90 from being
mis-classified as Strong.

Floor epsilon
-------------

We don't want 0 in any one dimension to nuke the composite to 0; the
gates handle the "stop the world" case. A tiny epsilon (1e-9) keeps
gradients usable for the demo without changing the reference outputs
to the displayed precision.
"""
from __future__ import annotations

from typing import Optional

from contract import DEFAULT_WEIGHTS

# Floor used to keep the geometric mean defined when a sub-metric is 0.
# We don't want 0 in any one dimension to nuke the composite to 0; the
# gates handle the "stop the world" case. Tiny epsilon keeps gradients
# usable for the demo without changing the reference outputs.
_EPS = 1e-9


def composite(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
) -> float:
    """Weighted geometric mean × 100.

    DPI-LS = 100 · ∏ m_i ^ w_i  with  Σ w_i = 1.

    Metrics with value None are skipped AND their weight is
    redistributed proportionally across present metrics. This
    preserves the unit-mean invariant when Q is missing pending
    conversational capture.
    """
    weights = weights or DEFAULT_WEIGHTS
    present = {k: v for k, v in metrics.items() if v is not None}
    if not present:
        return 0.0

    total_weight = sum(weights[k] for k in present)
    if total_weight <= 0:
        return 0.0

    product = 1.0
    for k, v in present.items():
        w = weights[k] / total_weight
        product *= max(float(v), _EPS) ** w
    return 100.0 * product
