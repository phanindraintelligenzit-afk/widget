"""Repository functions — DB operations for the API layer to call.

Kept as plain functions, not classes. Sessions are passed in, never
created here, so the API controls transaction scope.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from contract import AgentObservation, PartialObservation, Rating, Settings

from .models import (
    AgentRow,
    ObservationRow,
    PartialObservationRow,
    ScoreRow,
    SettingsRow,
    SMERatingRow,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---- agents --------------------------------------------------------------

def upsert_agent(
    s: Session,
    agent_id: str,
    agent_name: str,
    baseline: Optional[float] = None,
) -> AgentRow:
    row = s.get(AgentRow, agent_id)
    if row is None:
        row = AgentRow(
            id=agent_id,
            name=agent_name,
            baseline_human_output=baseline if baseline is not None else 100.0,
        )
        s.add(row)
    else:
        row.name = agent_name
        row.last_seen = _utcnow()
        if baseline is not None:
            row.baseline_human_output = baseline
    s.flush()
    return row


def list_agents(s: Session) -> list[AgentRow]:
    return list(s.scalars(select(AgentRow).order_by(AgentRow.name)))


# ---- observations --------------------------------------------------------

def save_observation(s: Session, obs: AgentObservation) -> ObservationRow:
    row = ObservationRow(
        agent_id=obs.agent_id,
        period_start=obs.period_start,
        period_end=obs.period_end,
        source=obs.source,
        payload=obs.model_dump(mode="json"),
    )
    s.add(row)
    s.flush()
    return row


# ---- partial observations -----------------------------------------------

def save_partial(s: Session, partial: PartialObservation) -> PartialObservationRow:
    row = PartialObservationRow(
        agent_id=partial.agent_id,
        source=partial.source,
        period_start=partial.period_start,
        period_end=partial.period_end,
        payload=partial.model_dump(mode="json"),
    )
    s.add(row)
    s.flush()
    return row


def partials_for_agent(s: Session, agent_id: str) -> list[PartialObservation]:
    """Return all stored partials for an agent in chronological order."""
    rows = list(
        s.scalars(
            select(PartialObservationRow)
            .where(PartialObservationRow.agent_id == agent_id)
            .order_by(PartialObservationRow.received_at.asc(), PartialObservationRow.id.asc())
        )
    )
    return [PartialObservation.model_validate(r.payload) for r in rows]


# ---- score history -------------------------------------------------------

def save_score(
    s: Session,
    agent_id: str,
    observation_id: int,
    rating: Rating,
) -> ScoreRow:
    row = ScoreRow(
        agent_id=agent_id,
        observation_id=observation_id,
        score=rating.score,
        raw_score=rating.raw_score,
        band=rating.band,
        unsafe=rating.unsafe,
        gate_failures=list(rating.gate_failures),
        metrics=dict(rating.metrics),
        missing=list(rating.missing),
    )
    s.add(row)
    s.flush()
    return row


def latest_score(s: Session, agent_id: str) -> Optional[ScoreRow]:
    return s.scalars(
        select(ScoreRow)
        .where(ScoreRow.agent_id == agent_id)
        .order_by(ScoreRow.computed_at.desc(), ScoreRow.id.desc())
        .limit(1)
    ).first()


def score_history(s: Session, agent_id: str, limit: int = 100) -> list[ScoreRow]:
    return list(
        s.scalars(
            select(ScoreRow)
            .where(ScoreRow.agent_id == agent_id)
            .order_by(ScoreRow.computed_at.desc(), ScoreRow.id.desc())
            .limit(limit)
        )
    )


def latest_scores_for_all(s: Session) -> list[tuple[AgentRow, Optional[ScoreRow]]]:
    return [(a, latest_score(s, a.id)) for a in list_agents(s)]


# ---- settings ------------------------------------------------------------

def get_settings(s: Session) -> Settings:
    row = s.get(SettingsRow, 1)
    if row is None:
        return Settings()
    return Settings.model_validate(row.payload)


def save_settings(s: Session, settings: Settings) -> SettingsRow:
    row = s.get(SettingsRow, 1)
    payload = settings.model_dump(mode="json")
    if row is None:
        row = SettingsRow(id=1, payload=payload)
        s.add(row)
    else:
        row.payload = payload
        row.updated_at = _utcnow()
    s.flush()
    return row


# ---- SME ratings (placeholder for M6) ------------------------------------

def save_sme_rating(
    s: Session,
    agent_id: str,
    accuracy: float,
    consistency: float,
    hallucination_rate: float,
    submitted_by: str,
) -> SMERatingRow:
    row = SMERatingRow(
        agent_id=agent_id,
        accuracy=accuracy,
        consistency=consistency,
        hallucination_rate=hallucination_rate,
        submitted_by=submitted_by,
    )
    s.add(row)
    s.flush()
    return row


def latest_sme_rating(s: Session, agent_id: str) -> Optional[SMERatingRow]:
    return s.scalars(
        select(SMERatingRow)
        .where(SMERatingRow.agent_id == agent_id)
        .order_by(SMERatingRow.submitted_at.desc(), SMERatingRow.id.desc())
        .limit(1)
    ).first()
