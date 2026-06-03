"""Engine output schema. Public so adapters/api can return it directly."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Rating(BaseModel):
    score: float                          # final, post-gate
    raw_score: float                      # pre-gate composite
    band: str                             # Exceptional | Strong | Needs Optimization | Underperforming
    unsafe: bool                          # any compliance gate fired
    gate_failures: list[str] = Field(default_factory=list)
    metrics: dict[str, Optional[float]]   # the 7 normalized inputs (Q may be None)
    missing: list[str] = Field(default_factory=list)  # metrics that need conversational input
