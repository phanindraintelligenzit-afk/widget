"""HTTP request/response schemas — kept thin. Most of the wire shape is
already the canonical contract."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentSummary(BaseModel):
    agent_id: str
    agent_name: str
    baseline_human_output: float
    first_seen: datetime
    last_seen: datetime


class HistoryPoint(BaseModel):
    score: float
    raw_score: float
    band: str
    unsafe: bool
    computed_at: datetime


class BoardRow(BaseModel):
    """One row on the live board widget."""
    agent_id: str
    agent_name: str
    score: float
    band: str
    unsafe: bool
    gate_failures: list[str] = Field(default_factory=list)
    computed_at: datetime


class SMERatingIn(BaseModel):
    agent_id: str
    accuracy: float
    consistency: float
    hallucination_rate: float
    submitted_by: str


class AdapterInfo(BaseModel):
    name: str


class SMEFlowStart(BaseModel):
    agent_id: str
    submitted_by: str


class SMEFlowRespond(BaseModel):
    response: str


class SMEFlowStatus(BaseModel):
    session_id: str
    agent_id: str
    step: str                              # ask_accuracy | … | done
    prompt: str
    complete: bool
    committed: bool                        # True once review = yes + persisted
    error: Optional[str] = None
    captured: dict[str, Optional[float]]   # the running review summary
    rating: Optional["Rating"] = None      # set when commit happens


# Forward ref import avoids circular load.
from contract import Rating  # noqa: E402
SMEFlowStatus.model_rebuild()
