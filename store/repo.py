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
    SMEFlowSessionRow,
    SMERatingRow,
    ValidationMetricRow,
    AgentValidationRuleRow,
    AgentValidationValueRow,
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
        # Explicitly set first_seen and last_seen at insert time.
        # Relying solely on the column default can leave them None before
        # the row is flushed/committed when autoflush=False.
        now = _utcnow()
        row = AgentRow(
            id=agent_id,
            name=agent_name,
            baseline_human_output=baseline if baseline is not None else 1.0,
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
    # Persist the rating's typed fields straight through — the contract
    # is the source of truth. The DB columns match the Pydantic model
    # field types (int count, float ratio, list[str] reasons).
    cap_reasons_list = (
        list(rating.cap_reasons) if rating.cap_reasons
        else ([rating.cap_reason] if rating.cap_reason else [])
    )
    row = ScoreRow(
        agent_id=agent_id,
        observation_id=observation_id,
        score=rating.score,
        raw_score=rating.raw_score,
        band=rating.band,
        unsafe=rating.unsafe,
        gate_failures=list(rating.gate_failures),
        metrics=dict(rating.metrics),
        sub_metrics=dict(rating.sub_metrics),
        missing=list(rating.missing),
        dimensions_measured=int(rating.dimensions_measured),
        coverage=float(rating.coverage),
        coverage_capped=bool(rating.capped or rating.coverage_capped),
        cap_reasons=cap_reasons_list,
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
    """Return (AgentRow, latest ScoreRow or None) for every agent.

    Uses a single LEFT JOIN query instead of one query per agent (N+1
    pattern). The subquery picks the highest ScoreRow.id per agent —
    because ids are autoincrement, max(id) == most recently inserted row.
    """
    from sqlalchemy import func

    # Subquery: one row per agent containing its latest score's id.
    latest_id_subq = (
        select(
            ScoreRow.agent_id.label("agent_id"),
            func.max(ScoreRow.id).label("latest_id"),
        )
        .group_by(ScoreRow.agent_id)
        .subquery("_latest_score_ids")
    )

    stmt = (
        select(AgentRow, ScoreRow)
        .outerjoin(latest_id_subq, AgentRow.id == latest_id_subq.c.agent_id)
        .outerjoin(ScoreRow, ScoreRow.id == latest_id_subq.c.latest_id)
        .order_by(AgentRow.name)
    )

    return [(row.AgentRow, row.ScoreRow) for row in s.execute(stmt).all()]


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


# ---- SME flow sessions ---------------------------------------------------

def create_sme_session(
    s: Session, session_id: str, agent_id: str, state_payload: dict
) -> SMEFlowSessionRow:
    row = SMEFlowSessionRow(id=session_id, agent_id=agent_id, state=state_payload)
    s.add(row)
    s.flush()
    return row


def get_sme_session(s: Session, session_id: str) -> Optional[SMEFlowSessionRow]:
    return s.get(SMEFlowSessionRow, session_id)


def update_sme_session(s: Session, session_id: str, state_payload: dict) -> SMEFlowSessionRow:
    row = s.get(SMEFlowSessionRow, session_id)
    if row is None:
        raise KeyError(f"SME flow session '{session_id}' not found")
    row.state = state_payload
    row.updated_at = _utcnow()
    s.flush()
    return row


# ---- dynamic validation components ---------------------------------------

def save_validation_metric(
    s: Session,
    metric_id: str,
    metric_name: str,
    category: str,
    description: str | None = None,
    source_system: str | None = None,
) -> ValidationMetricRow:
    row = s.get(ValidationMetricRow, metric_id)
    if row is None:
        row = ValidationMetricRow(
            id=metric_id,
            metric_name=metric_name,
            category=category,
            description=description,
            source_system=source_system,
        )
        s.add(row)
    else:
        row.metric_name = metric_name
        row.category = category
        row.description = description
        row.source_system = source_system
    s.flush()
    return row


def get_validation_metric(s: Session, metric_id: str) -> Optional[ValidationMetricRow]:
    return s.get(ValidationMetricRow, metric_id)


def list_validation_metrics(s: Session) -> list[ValidationMetricRow]:
    return list(s.scalars(select(ValidationMetricRow).order_by(ValidationMetricRow.id)))


def save_agent_validation_rule(
    s: Session,
    agent_id: str,
    metric_id: str,
    operator: str,
    threshold: float,
    enabled: bool = True,
) -> AgentValidationRuleRow:
    # Look for existing rule for this agent + metric
    row = s.scalars(
        select(AgentValidationRuleRow)
        .where(
            AgentValidationRuleRow.agent_id == agent_id,
            AgentValidationRuleRow.metric_id == metric_id,
        )
        .limit(1)
    ).first()

    if row is None:
        row = AgentValidationRuleRow(
            agent_id=agent_id,
            metric_id=metric_id,
            operator=operator,
            threshold=threshold,
            enabled=enabled,
        )
        s.add(row)
    else:
        row.operator = operator
        row.threshold = threshold
        row.enabled = enabled
    s.flush()
    return row


def list_agent_validation_rules(s: Session, agent_id: str) -> list[AgentValidationRuleRow]:
    return list(
        s.scalars(
            select(AgentValidationRuleRow)
            .where(AgentValidationRuleRow.agent_id == agent_id)
            .order_by(AgentValidationRuleRow.id)
        )
    )


def save_agent_validation_value(
    s: Session,
    agent_id: str,
    metric_id: str,
    value: float,
    period_start: datetime,
    period_end: datetime,
) -> AgentValidationValueRow:
    row = AgentValidationValueRow(
        agent_id=agent_id,
        metric_id=metric_id,
        value=value,
        period_start=period_start,
        period_end=period_end,
    )
    s.add(row)
    s.flush()
    return row


def list_agent_validation_values(
    s: Session,
    agent_id: str,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> list[AgentValidationValueRow]:
    stmt = select(AgentValidationValueRow).where(AgentValidationValueRow.agent_id == agent_id)
    if period_start:
        stmt = stmt.where(AgentValidationValueRow.period_end >= period_start)
    if period_end:
        stmt = stmt.where(AgentValidationValueRow.period_start <= period_end)
    return list(s.scalars(stmt.order_by(AgentValidationValueRow.period_start.asc())))


def latest_observation(s: Session, agent_id: str) -> Optional[ObservationRow]:
    """Return the most recently saved canonical observation for an agent."""
    return s.scalars(
        select(ObservationRow)
        .where(ObservationRow.agent_id == agent_id)
        .order_by(ObservationRow.received_at.desc(), ObservationRow.id.desc())
        .limit(1)
    ).first()
