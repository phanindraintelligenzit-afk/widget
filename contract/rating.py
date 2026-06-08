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

    # Coverage — guards against "score 100 from only one dimension reported."
    dimensions_measured: list[str] = Field(default_factory=list)  # present metric keys
    coverage: int = 0                     # len(dimensions_measured) — 0..7
    coverage_capped: bool = False         # True when band was capped due to low coverage
    cap_reasons: list[str] = Field(default_factory=list)  # human-readable explanation per cap

    # RAG signals — populated from the observation's retrievals field.
    # Doesn't affect the score; surfaced on the per-agent card.
    retrievals: int = 0
    retrieved_docs_total: int = 0
