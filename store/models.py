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


class ValidationMetricRow(Base):
    """Registry of dynamic validation metrics."""
    __tablename__ = "validation_metrics"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(1024), nullable=True)
    source_system: Mapped[str] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentValidationRuleRow(Base):
    """Configured validation rules per agent."""
    __tablename__ = "agent_validation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    metric_id: Mapped[str] = mapped_column(String(128), ForeignKey("validation_metrics.id"), index=True)
    operator: Mapped[str] = mapped_column(String(16))  # gte, lte, eq
    threshold: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentValidationValueRow(Base):
    """Ingested validation run values."""
    __tablename__ = "agent_validation_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    metric_id: Mapped[str] = mapped_column(String(128), ForeignKey("validation_metrics.id"), index=True)
    value: Mapped[float] = mapped_column(Float)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CostMetricDefinitionRow(Base):
    """Registry of cost metric definitions."""
    __tablename__ = "cost_metric_definitions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), index=True)  # ai, human, system, business
    display_name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(String(1024), nullable=True)
    source_system: Mapped[str] = mapped_column(String(128), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=True)


class AgentCostValueRow(Base):
    """Dynamic cost values ingested per agent, metric, and period."""
    __tablename__ = "agent_cost_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), ForeignKey("agents.id"), index=True)
    metric_id: Mapped[str] = mapped_column(String(128), ForeignKey("cost_metric_definitions.id"), index=True)
    value: Mapped[float] = mapped_column(Float)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

