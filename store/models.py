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
    missing: Mapped[list[str]] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class SettingsRow(Base):
    __tablename__ = "settings"

    # Singleton row. id is always 1.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
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
