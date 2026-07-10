"""DPI-LS rating bands.

A score of 0–100 maps to one of four bands. The bands are the public
output of the engine — the compliance gate and the completeness cap
both use the top of "Needs Optimization" (69) as their hard floor so
that a broken-gate or under-measured agent can never present as
Strong or Exceptional.

Bands
-----

* **Exceptional**         85–100
* **Strong**              70–84
* **Needs Optimization**  50–69   (top of band = the cap for gates and completeness)
* **Underperforming**     0–49
"""
from __future__ import annotations

# The cap value used by both the compliance gate (engine.gates) and the
# completeness cap (engine.completeness). Exposed here so a test or
# caller that wants the band floor has a single import.
NEEDS_OPT_CAP = 69.0

# Band names — public constants for callers that want to avoid
# stringly-typed comparisons.
EXCEPTIONAL = "Exceptional"
STRONG = "Strong"
NEEDS_OPTIMIZATION = "Needs Optimization"
UNDERPERFORMING = "Underperforming"


def band(score: float) -> str:
    """Map a 0–100 score to its band."""
    if score >= 85:
        return EXCEPTIONAL
    if score >= 70:
        return STRONG
    if score >= 50:
        return NEEDS_OPTIMIZATION
    return UNDERPERFORMING
