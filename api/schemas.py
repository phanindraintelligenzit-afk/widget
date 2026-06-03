"""HTTP request/response schemas — kept thin. Most of the wire shape is
already the canonical contract."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
    computed_at: datetime


class SMERatingIn(BaseModel):
    agent_id: str
    accuracy: float
    consistency: float
    hallucination_rate: float
    submitted_by: str


class AdapterInfo(BaseModel):
    name: str
