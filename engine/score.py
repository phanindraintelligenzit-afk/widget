"""Composite score — weighted geometric mean of the 7 sub-metrics × 100.

One model. Not a weighted sum. Weights live in Settings.
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

    DPI-LS = 100 · ∏ m_i^w_i  with  Σ w_i = 1.

    Metrics with value None are skipped AND their weight is redistributed
    proportionally across present metrics. This preserves the unit-mean
    invariant when Q is missing pending conversational capture.
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
