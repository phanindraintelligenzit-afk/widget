"""Hard compliance gates.

If G < 0.60 OR R < 0.50 OR V < 0.60 the rating is capped at the top of
the 'Needs Optimization' band (69) and flagged Unsafe — regardless of
score.

The Rating distinguishes between three different ways an agent
can end up in the "Needs Optimization" band (50-69):

1. **Organic 50-69 score**: Agent naturally scores in this range due to
   performance. Rating shows: capped=False, unsafe=False, no special flags.

2. **Coverage-capped**: Agent would score higher but lacks sufficient
   measured dimensions. Rating shows: capped=True,
   cap_reason="low-coverage ...", unsafe=False. Raw score is preserved
   to show what the agent would have scored with full data.

3. **Compliance gate fired**: Agent fails critical safety thresholds
   (G/R/V). Rating shows: unsafe=True, gate_failures=["G", ...].
   capped may also be True (the gate cap and the completeness cap
   can both apply — the gate cap is the stricter of the two).

Precedence: Compliance gates take priority over coverage caps. If both
would apply, the agent is flagged unsafe and the cap_reason reflects
the gate failure.

Gate / band overlap (deliberate)
--------------------------------

The "Needs Optimization" band (50–69) overlaps the gate zone. A
compliance-gated agent is *capped at the top of that band* (69) and
flagged ``unsafe=True`` — the band it falls into is structurally
identical to an organically-scoring 50–69 agent, but the two are
distinguishable via the ``unsafe``, ``gate_failures``, ``capped``, and
``cap_reason`` fields on the ``Rating``.

Design rationale: the cap is intentionally permissive (only floor of
the band, not the floor of the rating) so that a healthy-looking score
above 69 still surfaces as "Needs Optimization" rather than "Strong"
when a safety floor is breached. A single G violation should not be
hidden under a Strong or Exceptional label.

Tunables (pending Ranga)
------------------------

* ``R_max``           — the denominator for R (incident risk).
                        Currently 10.0 in :data:`contract.DEFAULT_GATE_THRESHOLDS`.
* ``gate_thresholds`` — the per-metric floors. Currently
                        ``{"G": 0.60, "R": 0.50, "V": 0.60}``.
                        Lives in :class:`contract.Settings` and the
                        API persists it via ``PUT /settings``.

These are the spec defaults; deployment-specific values are
configured per-tenant via the settings API.
"""
from __future__ import annotations

from typing import Optional

from contract import DEFAULT_GATE_THRESHOLDS

# Top of the "Needs Optimization" band (50–69). Capping here guarantees
# the band lookup can't return Strong/Exceptional when a gate fires.
NEEDS_OPT_CAP = 69.0

# The set of metric keys subject to the hard compliance gate. These
# represent safety / governance / risk / validation floors that an
# agent must meet regardless of its raw score.
# NOTE: held pending Ranga — see module docstring.
GATED_METRICS: tuple[str, ...] = ("G", "R", "V")


def gate_check(
    metrics: dict[str, Optional[float]],
    thresholds: dict[str, float] | None = None,
) -> tuple[bool, list[str]]:
    """Return (gate_fired, failed_metric_names).

    Missing metrics (None) are deferred — the engine never reports a
    gate failure for a dimension it has not observed. This is what
    makes a single-source C-only agent safe: no G/R/V data → no
    gate fires, but the completeness cap still kicks in (see
    ``engine.completeness``).
    """
    thresholds = thresholds or DEFAULT_GATE_THRESHOLDS
    failed: list[str] = []
    for k, t in thresholds.items():
        v = metrics.get(k)
        if v is None:
            # Missing pending conversational capture — defer, don't fail.
            continue
        if v < t:
            failed.append(k)
    return (len(failed) > 0, failed)


def apply_gate(raw_score: float, gate_fired: bool) -> tuple[float, bool]:
    """Cap score at NEEDS_OPT_CAP if a gate fires; return (final, unsafe)."""
    if not gate_fired:
        return raw_score, False
    return min(raw_score, NEEDS_OPT_CAP), True
