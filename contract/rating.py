"""Engine output schema. Public so adapters/api can return it directly.

The ``Rating`` mirrors what the engine's :func:`engine.rate.rate`
produces and what the API + widget consume:

* ``metrics``           — the 7 normalized inputs (``P``..``C``); any may be None
* ``score``             — final score, post-cap (the public number)
* ``raw_score``         — pre-cap composite (what the engine computed before
                          compliance + completeness caps)
* ``band``              — ``Exceptional`` | ``Strong`` | ``Needs Optimization``
                          | ``Underperforming``
* ``unsafe``            — any compliance gate fired (G/R/V floors)
* ``gate_failures``     — which gate metrics fell below the floor
* ``capped``            — band was capped to ``Needs Optimization`` (either by
                          compliance gate or by low coverage)
* ``cap_reason``        — human-readable explanation for the cap (single
                          string — the most relevant reason)
* ``coverage``          — float 0..1 ratio of dimensions measured
* ``dimensions_measured`` — int 0..7 count of dimensions measured

Two additional compatibility fields are kept so the widget and the
DB layer don't have to round-trip types:

* ``coverage_capped``   — same boolean as ``capped`` (legacy name the widget
                          already renders)
* ``cap_reasons``       — list form of ``cap_reason`` (legacy name; always
                          ``[]`` or ``[cap_reason]``)

RAG signals — populated from the observation's ``retrievals`` field.
Doesn't affect the score; surfaced on the per-agent card.
"""
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
    dimensions_measured: int = 0          # count of present metric keys, 0..7
    coverage: float = 0.0                 # ratio of present metric keys, 0..1
    capped: bool = False                  # band was capped to Needs Optimization
    cap_reason: Optional[str] = None      # human-readable explanation of the cap

    # Legacy widget / DB field names — kept for back-compat with the
    # embedded widget and the persisted ``ScoreRow``. The engine sets
    # both forms so the consumer can pick whichever it likes.
    coverage_capped: bool = False         # mirror of ``capped`` for the widget
    cap_reasons: list[str] = Field(default_factory=list)  # mirror of ``[cap_reason]``

    # RAG signals — populated from the observation's retrievals field.
    # Doesn't affect the score; surfaced on the per-agent card.
    retrievals: int = 0
    retrieved_docs_total: int = 0
