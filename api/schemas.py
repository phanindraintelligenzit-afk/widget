"""HTTP request/response schemas — kept thin. Most of the wire shape is
already the canonical contract."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

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
    raw_score: float
    band: str
    unsafe: bool
    gate_failures: list[str] = Field(default_factory=list)
    metrics: dict[str, Optional[float]] = Field(default_factory=dict)
    weighted_metrics: dict[str, Optional[float]] = Field(default_factory=dict)
    weights_used: dict[str, float] = Field(default_factory=dict)
    sub_metrics: dict[str, Any] = Field(default_factory=dict)
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


class AgentCreate(BaseModel):
    agent_id: str
    agent_name: str
    baseline_human_output: float = 1.0


class AgentUpdate(BaseModel):
    agent_name: Optional[str] = None
    baseline_human_output: Optional[float] = None


class AgentOnboardingIn(BaseModel):
    description: Optional[str] = None
    agent_type: Optional[str] = None
    environment: Optional[str] = None
    agent_owner: Optional[str] = None
    business_owner_name: Optional[str] = None
    business_owner_email: Optional[str] = None
    technical_owner_name: Optional[str] = None
    technical_owner_email: Optional[str] = None
    digital_worker_role: Optional[str] = None
    responsibilities: Optional[str] = None
    business_function: Optional[str] = None
    department: Optional[str] = None
    scope: Optional[str] = None


class AgentOnboardingOut(AgentOnboardingIn):
    agent_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class ManagerRatingIn(BaseModel):
    manager_id: str
    review_period: Optional[str] = None
    rating: int
    comments: Optional[str] = None


class ManagerRatingOut(ManagerRatingIn):
    id: int
    agent_id: str
    submitted_at: datetime


class CustomerRatingIn(BaseModel):
    customer_id: Optional[str] = None
    task_id: Optional[str] = None
    rating: int
    feedback: Optional[str] = None


class CustomerRatingOut(CustomerRatingIn):
    id: int
    agent_id: str
    submitted_at: datetime


class AgentConfigurationIn(BaseModel):
    configuration_key: str
    configuration_value: str
    source: Optional[str] = None
    created_by: Optional[str] = None


class AgentConfigurationOut(AgentConfigurationIn):
    id: int
    agent_id: str
    effective_from: datetime
    version: int
    approval_status: str


class AgentKRAIn(BaseModel):
    kra_name: str
    target_value: float
    weight: float


class AgentKRAOut(AgentKRAIn):
    id: int
    agent_id: str
    created_at: datetime


class AgentStatusIn(BaseModel):
    status: str


# Forward ref import avoids circular load.
from contract import Rating  # noqa: E402
SMEFlowStatus.model_rebuild()
