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
    details: list[dict] = Field(default_factory=list)


class PolicyViolation(BaseModel):
    # New fields (Presidio/detect-secrets era)
    policy_name: Optional[str] = None  # User-friendly name: "EmailAddressLeaked", "AwsSecretKeyLeaked"
    source: Optional[str] = None  # Engine + entity: "nlpPiiDetection:email_address", "secretsScanning:awskeydetector"
    original_entity: Optional[str] = None  # Raw entity type: "EMAIL_ADDRESS", "AWSKeyDetector"

    # Legacy field (for backward compat with old regex rules)
    rule: Optional[str] = None  # Old-style rule name: "pii.email", "governance.missing_approval"

    when: datetime
    action_name: Optional[str] = None


class Policy(BaseModel):
    total_actions: int
    violations: list[PolicyViolation] = Field(default_factory=list)


class Incident(BaseModel):
    severity_weight: float
    frequency: float
    source: str
    risk_name: Optional[str] = None


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
    """Cost / efficiency inputs for the C dimension.

    Three numbers, nothing else — exactly what the per-agent card's C
    panel shows. The engine derives the per-output figure it actually
    needs (the ``human_cost_per_output / ai_cost_per_output`` ratio)
    from ``model_cost`` divided by the agent's ``tasks.completed``
    count, so callers don't have to pre-compute it.

    The dropped fields (``ai_cost_per_output``, ``cloud_cost``,
    ``systems_accessed``) were either a derived value or pure
    observability. Removing them keeps the contract aligned with the
    dashboard: what you see on the card is exactly what the model
    carries.
    """
    # Breakdown surfaced on the per-agent card.
    input_tokens: int = 0
    output_tokens: int = 0
    model_cost: float = 0.0
    number_of_llm_calls: int = 0
    Human_cost: float = 0.0


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
