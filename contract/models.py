"""Canonical telemetry contract.

Every adapter produces one (or many) AgentObservation. The engine reads
nothing else. Never import an agent framework into this file.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TaskStats(BaseModel):
    assigned: int
    completed: int
    failed: int
    pending_approval: int = 0
    blocked_no_access: int = 0


class Executions(BaseModel):
    attempts: int
    successful: int


class PolicyViolation(BaseModel):
    rule: str
    when: datetime


class Policy(BaseModel):
    total_actions: int
    violations: list[PolicyViolation] = Field(default_factory=list)


class Incident(BaseModel):
    severity_weight: float
    frequency: float
    source: str


class Quality(BaseModel):
    """Null at the observation level means 'needs conversational/SME input'.

    Engine must treat a missing Quality block as a signal to defer Q, not
    as zero.
    """
    accuracy: float
    consistency: float
    hallucination_rate: float


class Validation(BaseModel):
    required_components: int
    validated_components: int
    audit_ready: bool = False


class Cost(BaseModel):
    ai_cost_per_output: float
    tokens: int = 0
    cloud_cost: float = 0.0
    systems_accessed: int = 0


class AgentObservation(BaseModel):
    """Normalized snapshot of one agent over a period.

    All adapters MUST produce this and only this. Engine MUST consume only
    this. Fields may be None — engine treats null as 'needs input', never
    zero.
    """
    agent_id: str
    agent_name: str
    period_start: datetime
    period_end: datetime
    tasks: TaskStats
    executions: Executions
    policy: Policy
    incidents: list[Incident] = Field(default_factory=list)
    quality: Optional[Quality] = None
    validation: Validation
    cost: Cost
    source: str
    # Optional RAG-specific signals — populated by the dpi_ls LlamaIndex
    # and RAG patchers via the ``/ingest`` path. Not required for the
    # engine's score math (retrievals already count toward E); surfaced
    # on the per-agent card for observability.
    retrievals: int = 0
    retrieved_docs_total: int = 0
