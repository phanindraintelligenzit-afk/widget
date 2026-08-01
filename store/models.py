"""SQLAlchemy schema for observations, scores, settings, and SME ratings.

JSON columns keep the schema portable (SQLite for local dev, Postgres
JSONB equivalent in prod) without per-driver branching.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    baseline_human_output: Mapped[float] = mapped_column(Float, default=100.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ObservationRow(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class ScoreRow(Base):
    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    observation_id: Mapped[int] = mapped_column(Integer, ForeignKey("observations.id"))
    score: Mapped[float] = mapped_column(Float)
    raw_score: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(32))
    unsafe: Mapped[bool] = mapped_column(Boolean)
    gate_failures: Mapped[list[str]] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    weighted_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    weights_used: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sub_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    missing: Mapped[list[str]] = mapped_column(JSON)
    dimensions_measured: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[float] = mapped_column(Float, default=0.0)
    coverage_capped: Mapped[bool] = mapped_column(Boolean, default=False)
    cap_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class SettingsRow(Base):
    __tablename__ = "settings"

    # Singleton row. id is always 1.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PartialObservationRow(Base):
    """One source's contribution to an agent over a period.

    Stored separately from canonical observations so source streams can
    accumulate independently; the API merges latest-per-dimension at
    score time.
    """
    __tablename__ = "partial_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class SMEFlowSessionRow(Base):
    """In-progress conversational SME rating session.

    The state machine is in engine/sme_flow.py and stays pure; this row
    persists state across API calls so the conversation survives worker
    restarts.
    """
    __tablename__ = "sme_flow_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SMERatingRow(Base):
    """SME / QA conversational quality capture — input to Q for M6."""
    __tablename__ = "sme_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    accuracy: Mapped[float] = mapped_column(Float)
    consistency: Mapped[float] = mapped_column(Float)
    hallucination_rate: Mapped[float] = mapped_column(Float)
    submitted_by: Mapped[str] = mapped_column(String(128))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CostResourceRegistryRow(Base):
    """List of all evaluated cost resources."""
    __tablename__ = "cost_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CostResourceEvaluationRow(Base):
    """Runtime evaluation results per resource and metric."""
    __tablename__ = "cost_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(String(128), ForeignKey("cost_resource_registry.name"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class ValidationResourceRegistryRow(Base):
    """List of all evaluated validation resources."""
    __tablename__ = "validation_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ValidationResourceEvaluationRow(Base):
    """Runtime evaluation results per validation resource and metric."""
    __tablename__ = "validation_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(String(128), ForeignKey("validation_resource_registry.name"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class QualityResourceRegistryRow(Base):
    """List of all evaluated quality resources."""
    __tablename__ = "quality_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class QualityResourceEvaluationRow(Base):
    """Runtime evaluation results per quality resource and metric."""
    __tablename__ = "quality_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(String(128), ForeignKey("quality_resource_registry.name"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class ProductivityResourceRegistryRow(Base):
    """List of all evaluated productivity resources."""
    __tablename__ = "productivity_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ProductivityResourceEvaluationRow(Base):
    """Runtime evaluation results per productivity resource and metric."""
    __tablename__ = "productivity_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(String(128), ForeignKey("productivity_resource_registry.name"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)

class ExecutionResourceRegistryRow(Base):
    __tablename__ = "execution_resource_registry"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class ExecutionResourceEvaluationRow(Base):
    __tablename__ = "execution_resource_evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_name: Mapped[str] = mapped_column(String, index=True)
    metric: Mapped[str] = mapped_column(String, index=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String, nullable=True)
    current_value: Mapped[str] = mapped_column(String, nullable=True)
    last_run: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String, default="FAILED")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)

class RiskResourceRegistryRow(Base):
    """List of all evaluated risk resources."""
    __tablename__ = "risk_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RiskResourceEvaluationRow(Base):
    """Runtime evaluation results per risk resource and metric."""
    __tablename__ = "risk_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(String(128), ForeignKey("risk_resource_registry.name"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class RiskIncidentRow(Base):
    """Normalized incident representation for Risk computation."""
    __tablename__ = "risk_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(128))
    source_resource: Mapped[str] = mapped_column(String(128))
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(64))
    severity_weight: Mapped[float] = mapped_column(Float)
    frequency: Mapped[int] = mapped_column(Integer)
    risk_contribution: Mapped[float] = mapped_column(Float)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=True)
    span_id: Mapped[str] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(64), default="NORMALIZED")


class GovernanceIncidentRow(Base):
    """Normalized incident representation for Governance computation."""
    __tablename__ = "governance_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(128))
    source_resource: Mapped[str] = mapped_column(String(128))
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(64))
    severity_weight: Mapped[float] = mapped_column(Float)
    frequency: Mapped[int] = mapped_column(Integer)
    risk_contribution: Mapped[float] = mapped_column(Float)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=True)
    span_id: Mapped[str] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(64), default="NORMALIZED")


class GovernanceResourceRegistryRow(Base):
    """List of all evaluated governance resources."""
    __tablename__ = "governance_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_required: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GovernanceResourceEvaluationRow(Base):
    """Runtime evaluation results per governance resource and metric."""
    __tablename__ = "governance_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(String(128), ForeignKey("governance_resource_registry.name"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class EnterpriseValidationResourceRegistryRow(Base):
    """Enterprise Validation dimension registry — Guardrails AI, Pydantic
    AI, Instructor. Parallel to the existing ValidationResourceRegistryRow
    so the classic dimension keeps working unchanged (additive extension,
    never a replacement).
    """
    __tablename__ = "enterprise_validation_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=True)
    documentation_url: Mapped[str] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class EnterpriseValidationResourceEvaluationRow(Base):
    """Runtime evaluation of an enterprise validation metric — one row
    per (resource, canonical or native metric)."""
    __tablename__ = "enterprise_validation_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("enterprise_validation_resource_registry.name"),
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class EnterpriseQualityResourceRegistryRow(Base):
    """Enterprise Quality dimension registry — DeepEval, TruLens."""
    __tablename__ = "enterprise_quality_resource_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sdk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    integration_implemented: Mapped[bool] = mapped_column(Boolean, default=True)
    documentation_url: Mapped[str] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class EnterpriseQualityResourceEvaluationRow(Base):
    """Runtime evaluation of an enterprise quality metric — one row
    per (resource, canonical or native metric)."""
    __tablename__ = "enterprise_quality_resource_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_name: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("enterprise_quality_resource_registry.name"),
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(128))
    current_value: Mapped[str] = mapped_column(String(256), nullable=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(String(512), nullable=True)
    last_run: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[str] = mapped_column(String(64), default="PENDING")
    dashboard_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_executed: Mapped[bool] = mapped_column(Boolean, default=False)
