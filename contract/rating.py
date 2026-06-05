"""Engine output schema. Public so adapters/api can return it directly."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Rating(BaseModel):
    score: float                          # final, post-cap
    raw_score: float                      # pre-cap composite
    band: str                             # Exceptional | Strong | Needs Optimization | Underperforming
    unsafe: bool                          # any compliance gate fired (G/R/V floors)
    gate_failures: list[str] = Field(default_factory=list)
    metrics: dict[str, Optional[float]]   # the 7 normalized inputs (any may be None)
    missing: list[str] = Field(default_factory=list)  # metric keys not yet observed

    # Coverage fields as specified
    dimensions_measured: int = 0          # 7 - number of missing/null dimensions
    coverage: float = 0.0                 # round(dimensions_measured / 7, 3)
    capped: bool = False                  # True when band was capped
    cap_reason: Optional[str] = None      # reason for capping
