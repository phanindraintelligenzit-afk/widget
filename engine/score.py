"""Composite score — weighted arithmetic mean of the 7 sub-metrics × 100.

One model. Weights live in Settings.

The math
--------

::

    DPI-LS = 100 · Σ w_i · m_i   with  Σ w_i = 1   (over present metrics)

For the spec defaults ``P=.15, Q=.20, E=.15, G=.20, R=.15, V=.10, C=.05``
(sum 1.0), an agent scoring ``.85`` on every dimension gets
``100 · 0.85 = 85``. The four reference outputs (85, 92, 55) all
collapse cleanly to ``m · 100`` when the metrics are uniform.

Why arithmetic and not geometric
--------------------------------

A weighted arithmetic mean expresses "score reflects performance
across all 7 metrics" — a 0 in G lowers the score, but doesn't nuke
it to zero (a C=0 / Q=0 / P=0 agent still has 80% of the weight on
the dims it does well on, so the score is 80, not 0). This matches
the "total score based on all metrics" reading on the dashboard.

A weighted geometric mean (the previous formula) had the opposite
property: a single 0 in any dimension killed the entire product. The
safety-net was the gate force-cap (see ``engine.gates``), but the
resulting ``raw_score`` was so far below the gate cap that it gave
a misleading "Underperforming" impression. With arithmetic, the
``raw_score`` always reflects the 7-metric mean — and the gate cap
expresses the *band* the agent should sit in, not a performance
failure.

Weight redistribution
---------------------

Metrics with value ``None`` are skipped AND their weight is
redistributed proportionally across present metrics. This preserves
the unit-mean invariant when, for example, Q is missing pending
conversational capture. A C-only agent with ``C=0.9`` scores
``0.9 · 100 = 90`` — the right answer for the C slice but obviously
not "Strong". The completeness cap (see ``engine.completeness``) is
what keeps that 90 from being mis-classified as Strong.
"""
from __future__ import annotations

from typing import Optional

from contract import DEFAULT_WEIGHTS


def composite(
    metrics: dict[str, Optional[float]],
    weights: dict[str, float] | None = None,
) -> tuple[float, dict[str, float], dict[str, float]]:
    """Calculates the official DPI-LS geometric product score and linear weighted metrics.

    DPI-LS = (P * Q^1.5 * E) * (G^1.5 * R^2) * C * V * 100

    Returns:
        (raw_score, weighted_metrics, active_weights)
    """
    weights = weights or DEFAULT_WEIGHTS
    present = {k: v for k, v in metrics.items() if v is not None}
    
    if not present:
        return 0.0, {}, {}

    total_weight = sum(weights[k] for k in present)
    if total_weight <= 0:
        return 0.0, {}, {}

    active_weights = {k: weights[k] / total_weight for k in present}
    weighted_metrics = {k: active_weights[k] * float(v) for k, v in present.items()}

    raw_score = sum(weighted_metrics.values()) * 100.0

    return raw_score, weighted_metrics, active_weights
