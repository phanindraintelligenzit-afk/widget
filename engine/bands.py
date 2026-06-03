"""DPI-LS rating bands."""
from __future__ import annotations

EXCEPTIONAL = "Exceptional"
STRONG = "Strong"
NEEDS_OPTIMIZATION = "Needs Optimization"
UNDERPERFORMING = "Underperforming"


def band(score: float) -> str:
    if score >= 85:
        return EXCEPTIONAL
    if score >= 70:
        return STRONG
    if score >= 50:
        return NEEDS_OPTIMIZATION
    return UNDERPERFORMING
