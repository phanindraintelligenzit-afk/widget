"""Repository functions — DB operations for the API layer to call.

Kept as plain functions, not classes. Sessions are passed in, never
created here, so the API controls transaction scope.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
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
    CostResourceRegistryRow,
    CostResourceEvaluationRow,
    ValidationResourceRegistryRow,
    ValidationResourceEvaluationRow,
    QualityResourceRegistryRow,
    QualityResourceEvaluationRow,
    ProductivityResourceRegistryRow,
    ProductivityResourceEvaluationRow,
    ExecutionResourceRegistryRow,
    ExecutionResourceEvaluationRow,
    RiskResourceRegistryRow,
    RiskResourceEvaluationRow,
    RiskIncidentRow,
    AgentOnboardingRow,
    AgentKRARow,
    AgentConfigurationRow,
    ManagerRatingRow,
    CustomerRatingRow,
)

def list_latest_risk_incidents(s: Session) -> list[RiskIncidentRow]:
    return s.scalars(select(RiskIncidentRow)).all()



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
        weighted_metrics=dict(rating.weighted_metrics),
        weights_used=dict(rating.weights_used),
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
        raise RuntimeError("Engine uncalibrated: 'app_settings' missing from database. Run sensitivity harness to initialize.")
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


# ---- cost resource evaluation registry ------------------------------------

def upsert_cost_resource(
    s: Session,
    name: str,
    sdk_available: bool = False,
    api_available: bool = False,
    api_key_required: bool = False,
    integration_implemented: bool = False,
) -> CostResourceRegistryRow:
    row = s.scalars(
        select(CostResourceRegistryRow).where(CostResourceRegistryRow.name == name)
    ).first()
    if row is None:
        row = CostResourceRegistryRow(
            name=name,
            sdk_available=sdk_available,
            api_available=api_available,
            api_key_required=api_key_required,
            integration_implemented=integration_implemented,
        )
        s.add(row)
    else:
        row.sdk_available = sdk_available
        row.api_available = api_available
        row.api_key_required = api_key_required
        row.integration_implemented = integration_implemented
    s.flush()
    return row


def list_cost_resources(s: Session) -> list[CostResourceRegistryRow]:
    return list(s.scalars(select(CostResourceRegistryRow).order_by(CostResourceRegistryRow.name)))


def save_cost_resource_evaluation(
    s: Session,
    resource_name: str,
    metric: str,
    detected: bool,
    evidence: Optional[str],
    current_value: Optional[str] = None,
    status: str = "SUCCESS",
    dashboard_verified: bool = False,
    agent_executed: bool = False,
) -> CostResourceEvaluationRow:
    # Get latest evaluation to preserve dashboard_verified if not explicitly set
    existing = s.scalars(
        select(CostResourceEvaluationRow)
        .where(
            CostResourceEvaluationRow.resource_name == resource_name,
            CostResourceEvaluationRow.metric == metric,
        )
        .order_by(CostResourceEvaluationRow.last_run.desc())
        .limit(1)
    ).first()

    verified = dashboard_verified
    if existing and not dashboard_verified:
        verified = existing.dashboard_verified

    row = CostResourceEvaluationRow(
        resource_name=resource_name,
        metric=metric,
        current_value=current_value,
        detected=detected,
        evidence=evidence,
        last_run=_utcnow(),
        status=status,
        dashboard_verified=verified,
        agent_executed=agent_executed,
    )
    s.add(row)
    s.flush()
    return row


def list_latest_cost_resource_evaluations(s: Session) -> list[CostResourceEvaluationRow]:
    """Return the most recent evaluation row for each resource-metric pair."""
    from sqlalchemy import func
    subq = (
        select(
            CostResourceEvaluationRow.resource_name.label("rname"),
            CostResourceEvaluationRow.metric.label("met"),
            func.max(CostResourceEvaluationRow.id).label("max_id"),
        )
        .group_by(CostResourceEvaluationRow.resource_name, CostResourceEvaluationRow.metric)
        .subquery()
    )
    stmt = (
        select(CostResourceEvaluationRow)
        .join(
            subq,
            CostResourceEvaluationRow.id == subq.c.max_id
        )
        .order_by(CostResourceEvaluationRow.resource_name, CostResourceEvaluationRow.metric)
    )
    return list(s.scalars(stmt))


def verify_dashboard_cost_resource_evaluation(s: Session, resource_name: str, metric: Optional[str] = None) -> bool:
    """Flag evaluations for this resource (and optionally specific metric) as dashboard_verified."""
    query = select(CostResourceEvaluationRow).where(CostResourceEvaluationRow.resource_name == resource_name)
    if metric:
        query = query.where(CostResourceEvaluationRow.metric == metric)
        
    rows = list(s.scalars(query))
    if not rows:
        return False
    for r in rows:
        r.dashboard_verified = True
    s.flush()
    return True


# ---- validation resource evaluation registry ------------------------------------

def upsert_validation_resource(
    s: Session,
    name: str,
    sdk_available: bool = False,
    api_available: bool = False,
    api_key_required: bool = False,
    integration_implemented: bool = False,
) -> ValidationResourceRegistryRow:
    row = s.scalars(
        select(ValidationResourceRegistryRow).where(ValidationResourceRegistryRow.name == name)
    ).first()
    if row is None:
        row = ValidationResourceRegistryRow(
            name=name,
            sdk_available=sdk_available,
            api_available=api_available,
            api_key_required=api_key_required,
            integration_implemented=integration_implemented,
        )
        s.add(row)
    else:
        row.sdk_available = sdk_available
        row.api_available = api_available
        row.api_key_required = api_key_required
        row.integration_implemented = integration_implemented
    s.flush()
    return row


def list_validation_resources(s: Session) -> list[ValidationResourceRegistryRow]:
    return list(s.scalars(select(ValidationResourceRegistryRow).order_by(ValidationResourceRegistryRow.name)))


def save_validation_resource_evaluation(
    s: Session,
    resource_name: str,
    metric: str,
    detected: bool,
    evidence: Optional[str],
    current_value: Optional[str] = None,
    status: str = "SUCCESS",
    dashboard_verified: bool = False,
    agent_executed: bool = False,
) -> ValidationResourceEvaluationRow:
    existing = s.scalars(
        select(ValidationResourceEvaluationRow)
        .where(
            ValidationResourceEvaluationRow.resource_name == resource_name,
            ValidationResourceEvaluationRow.metric == metric,
        )
        .order_by(ValidationResourceEvaluationRow.last_run.desc())
        .limit(1)
    ).first()

    verified = dashboard_verified
    if existing and not dashboard_verified:
        verified = existing.dashboard_verified

    row = ValidationResourceEvaluationRow(
        resource_name=resource_name,
        metric=metric,
        current_value=current_value,
        detected=detected,
        evidence=evidence,
        last_run=_utcnow(),
        status=status,
        dashboard_verified=verified,
        agent_executed=agent_executed,
    )
    s.add(row)
    s.flush()
    return row


def list_latest_validation_resource_evaluations(s: Session) -> list[ValidationResourceEvaluationRow]:
    """Return the most recent evaluation row for each validation resource-metric pair."""
    from sqlalchemy import func
    subq = (
        select(
            ValidationResourceEvaluationRow.resource_name.label("rname"),
            ValidationResourceEvaluationRow.metric.label("met"),
            func.max(ValidationResourceEvaluationRow.id).label("max_id"),
        )
        .group_by(ValidationResourceEvaluationRow.resource_name, ValidationResourceEvaluationRow.metric)
        .subquery()
    )
    stmt = (
        select(ValidationResourceEvaluationRow)
        .join(
            subq,
            ValidationResourceEvaluationRow.id == subq.c.max_id
        )
        .order_by(ValidationResourceEvaluationRow.resource_name, ValidationResourceEvaluationRow.metric)
    )
    return list(s.scalars(stmt))


def verify_dashboard_validation_resource_evaluation(s: Session, resource_name: str, metric: Optional[str] = None) -> bool:
    """Flag evaluations for this validation resource (and optionally specific metric) as dashboard_verified."""
    query = select(ValidationResourceEvaluationRow).where(ValidationResourceEvaluationRow.resource_name == resource_name)
    if metric:
        query = query.where(ValidationResourceEvaluationRow.metric == metric)
        
    rows = list(s.scalars(query))
    if not rows:
        return False
    for r in rows:
        r.dashboard_verified = True
    s.flush()
    return True


def upsert_quality_resource(
    s: Session,
    name: str,
    sdk_available: bool = False,
    api_available: bool = False,
    api_key_required: bool = False,
    integration_implemented: bool = False,
) -> QualityResourceRegistryRow:
    row = s.scalars(
        select(QualityResourceRegistryRow).where(QualityResourceRegistryRow.name == name)
    ).first()
    if row is None:
        row = QualityResourceRegistryRow(
            name=name,
            sdk_available=sdk_available,
            api_available=api_available,
            api_key_required=api_key_required,
            integration_implemented=integration_implemented,
        )
        s.add(row)
    else:
        row.sdk_available = sdk_available
        row.api_available = api_available
        row.api_key_required = api_key_required
        row.integration_implemented = integration_implemented
    s.flush()
    return row


def list_quality_resources(s: Session) -> list[QualityResourceRegistryRow]:
    return list(s.scalars(select(QualityResourceRegistryRow).order_by(QualityResourceRegistryRow.name)))


def save_quality_resource_evaluation(
    s: Session,
    resource_name: str,
    metric: str,
    detected: bool,
    evidence: Optional[str],
    current_value: Optional[str] = None,
    status: str = "SUCCESS",
    dashboard_verified: bool = False,
    agent_executed: bool = False,
) -> QualityResourceEvaluationRow:
    existing = s.scalars(
        select(QualityResourceEvaluationRow)
        .where(
            QualityResourceEvaluationRow.resource_name == resource_name,
            QualityResourceEvaluationRow.metric == metric,
        )
        .order_by(QualityResourceEvaluationRow.last_run.desc())
        .limit(1)
    ).first()

    verified = dashboard_verified
    if existing and not dashboard_verified:
        verified = existing.dashboard_verified

    row = QualityResourceEvaluationRow(
        resource_name=resource_name,
        metric=metric,
        current_value=current_value,
        detected=detected,
        evidence=evidence,
        last_run=_utcnow(),
        status=status,
        dashboard_verified=verified,
        agent_executed=agent_executed,
    )
    s.add(row)
    s.flush()
    return row


def list_latest_quality_resource_evaluations(s: Session) -> list[QualityResourceEvaluationRow]:
    """Return the most recent evaluation row for each quality resource-metric pair."""
    from sqlalchemy import func
    subq = (
        select(
            QualityResourceEvaluationRow.resource_name.label("rname"),
            QualityResourceEvaluationRow.metric.label("met"),
            func.max(QualityResourceEvaluationRow.id).label("max_id"),
        )
        .group_by(QualityResourceEvaluationRow.resource_name, QualityResourceEvaluationRow.metric)
        .subquery()
    )
    stmt = (
        select(QualityResourceEvaluationRow)
        .join(
            subq,
            QualityResourceEvaluationRow.id == subq.c.max_id
        )
        .order_by(QualityResourceEvaluationRow.resource_name, QualityResourceEvaluationRow.metric)
    )
    return list(s.scalars(stmt))


def verify_dashboard_quality_resource_evaluation(s: Session, resource_name: str, metric: Optional[str] = None) -> bool:
    """Flag evaluations for this quality resource (and optionally specific metric) as dashboard_verified."""
    query = select(QualityResourceEvaluationRow).where(QualityResourceEvaluationRow.resource_name == resource_name)
    if metric:
        query = query.where(QualityResourceEvaluationRow.metric == metric)
        
    rows = list(s.scalars(query))
    if not rows:
        return False
    for r in rows:
        r.dashboard_verified = True
    s.flush()
    return True


# ---- productivity resource evaluation registry ------------------------------------

def upsert_productivity_resource(
    s: Session,
    name: str,
    sdk_available: bool = False,
    api_available: bool = False,
    api_key_required: bool = False,
    integration_implemented: bool = False,
) -> ProductivityResourceRegistryRow:
    row = s.scalars(
        select(ProductivityResourceRegistryRow).where(ProductivityResourceRegistryRow.name == name)
    ).first()
    if row is None:
        row = ProductivityResourceRegistryRow(
            name=name,
            sdk_available=sdk_available,
            api_available=api_available,
            api_key_required=api_key_required,
            integration_implemented=integration_implemented,
        )
        s.add(row)
    else:
        row.sdk_available = sdk_available
        row.api_available = api_available
        row.api_key_required = api_key_required
        row.integration_implemented = integration_implemented
    s.flush()
    return row


def list_productivity_resources(s: Session) -> list[ProductivityResourceRegistryRow]:
    return list(s.scalars(select(ProductivityResourceRegistryRow).order_by(ProductivityResourceRegistryRow.name)))


def save_productivity_resource_evaluation(
    s: Session,
    resource_name: str,
    metric: str,
    detected: bool,
    evidence: Optional[str],
    current_value: Optional[str] = None,
    status: str = "SUCCESS",
    dashboard_verified: bool = False,
    agent_executed: bool = False,
) -> ProductivityResourceEvaluationRow:
    existing = s.scalars(
        select(ProductivityResourceEvaluationRow)
        .where(
            ProductivityResourceEvaluationRow.resource_name == resource_name,
            ProductivityResourceEvaluationRow.metric == metric,
        )
        .order_by(ProductivityResourceEvaluationRow.last_run.desc())
        .limit(1)
    ).first()

    verified = dashboard_verified
    if existing and not dashboard_verified:
        verified = existing.dashboard_verified

    row = ProductivityResourceEvaluationRow(
        resource_name=resource_name,
        metric=metric,
        current_value=current_value,
        detected=detected,
        evidence=evidence,
        last_run=_utcnow(),
        status=status,
        dashboard_verified=verified,
        agent_executed=agent_executed,
    )
    s.add(row)
    s.flush()
    return row


def list_latest_productivity_resource_evaluations(s: Session) -> list[ProductivityResourceEvaluationRow]:
    """Return the most recent evaluation row for each productivity resource-metric pair."""
    from sqlalchemy import func
    subq = (
        select(
            ProductivityResourceEvaluationRow.resource_name.label("rname"),
            ProductivityResourceEvaluationRow.metric.label("met"),
            func.max(ProductivityResourceEvaluationRow.id).label("max_id"),
        )
        .group_by(ProductivityResourceEvaluationRow.resource_name, ProductivityResourceEvaluationRow.metric)
        .subquery()
    )
    stmt = (
        select(ProductivityResourceEvaluationRow)
        .join(
            subq,
            ProductivityResourceEvaluationRow.id == subq.c.max_id
        )
        .order_by(ProductivityResourceEvaluationRow.resource_name, ProductivityResourceEvaluationRow.metric)
    )
    return list(s.scalars(stmt))


def verify_dashboard_productivity_resource_evaluation(s: Session, resource_name: str, metric: Optional[str] = None) -> bool:
    """Flag evaluations for this productivity resource (and optionally specific metric) as dashboard_verified."""
    query = select(ProductivityResourceEvaluationRow).where(ProductivityResourceEvaluationRow.resource_name == resource_name)
    if metric:
        query = query.where(ProductivityResourceEvaluationRow.metric == metric)
        
    rows = list(s.scalars(query))
    if not rows:
        return False
    for r in rows:
        r.dashboard_verified = True
    s.flush()
    return True

def list_execution_resources(session: Session) -> Sequence[ExecutionResourceRegistryRow]:
    return session.scalars(select(ExecutionResourceRegistryRow).order_by(ExecutionResourceRegistryRow.name)).all()

def upsert_execution_resource(session: Session, name: str, sdk_available: bool, api_available: bool, api_key_required: bool, integration_implemented: bool) -> ExecutionResourceRegistryRow:
    row = session.scalars(select(ExecutionResourceRegistryRow).where(ExecutionResourceRegistryRow.name == name)).first()
    if not row:
        row = ExecutionResourceRegistryRow(name=name)
        session.add(row)
    row.sdk_available = sdk_available
    row.api_available = api_available
    row.api_key_required = api_key_required
    row.integration_implemented = integration_implemented
    return row

def save_execution_resource_evaluation(session: Session, resource_name: str, metric: str, detected: bool, evidence: str, current_value: str, status: str, agent_executed: bool = False) -> ExecutionResourceEvaluationRow:
    row = ExecutionResourceEvaluationRow(
        resource_name=resource_name,
        metric=metric,
        detected=detected,
        evidence=evidence,
        current_value=current_value,
        status=status,
        agent_executed=agent_executed,
    )
    session.add(row)
    return row

def list_latest_execution_resource_evaluations(session: Session) -> list[ExecutionResourceEvaluationRow]:
    subq = (
        select(
            ExecutionResourceEvaluationRow.resource_name,
            ExecutionResourceEvaluationRow.metric,
            func.max(ExecutionResourceEvaluationRow.id).label("max_id")
        )
        .group_by(ExecutionResourceEvaluationRow.resource_name, ExecutionResourceEvaluationRow.metric)
        .subquery()
    )
    rows = session.scalars(
        select(ExecutionResourceEvaluationRow)
        .join(subq, ExecutionResourceEvaluationRow.id == subq.c.max_id)
    ).all()
    return list(rows)

def verify_dashboard_execution_resource_evaluation(session: Session, resource_name: str, metric: str = None) -> bool:
    q = select(ExecutionResourceEvaluationRow).where(ExecutionResourceEvaluationRow.resource_name == resource_name)
    if metric:
        q = q.where(ExecutionResourceEvaluationRow.metric == metric)
    q = q.order_by(ExecutionResourceEvaluationRow.id.desc()).limit(1)
    row = session.scalars(q).first()
    if row:
        row.dashboard_verified = True
    return False


# ---- Task 1: Enterprise Digital Worker Management ----

def upsert_agent_onboarding(s: Session, agent_id: str, payload: dict) -> AgentOnboardingRow:
    row = s.scalars(select(AgentOnboardingRow).where(AgentOnboardingRow.agent_id == agent_id)).first()
    if not row:
        row = AgentOnboardingRow(agent_id=agent_id)
        s.add(row)
    
    for key, value in payload.items():
        if hasattr(row, key) and value is not None:
            setattr(row, key, value)
            
    row.updated_at = _utcnow()
    s.flush()
    return row

def get_agent_onboarding(s: Session, agent_id: str) -> Optional[AgentOnboardingRow]:
    return s.scalars(select(AgentOnboardingRow).where(AgentOnboardingRow.agent_id == agent_id)).first()

def save_manager_rating(s: Session, agent_id: str, manager_id: str, rating: int, comments: Optional[str] = None, review_period: Optional[str] = None) -> ManagerRatingRow:
    row = ManagerRatingRow(
        agent_id=agent_id,
        manager_id=manager_id,
        rating=rating,
        comments=comments,
        review_period=review_period
    )
    s.add(row)
    s.flush()
    return row

def get_manager_ratings(s: Session, agent_id: str) -> list[ManagerRatingRow]:
    return list(s.scalars(select(ManagerRatingRow).where(ManagerRatingRow.agent_id == agent_id).order_by(ManagerRatingRow.submitted_at.desc())))

def save_customer_rating(s: Session, agent_id: str, rating: int, customer_id: Optional[str] = None, task_id: Optional[str] = None, feedback: Optional[str] = None) -> CustomerRatingRow:
    row = CustomerRatingRow(
        agent_id=agent_id,
        customer_id=customer_id,
        task_id=task_id,
        rating=rating,
        feedback=feedback
    )
    s.add(row)
    s.flush()
    return row

def get_customer_ratings(s: Session, agent_id: str) -> list[CustomerRatingRow]:
    return list(s.scalars(select(CustomerRatingRow).where(CustomerRatingRow.agent_id == agent_id).order_by(CustomerRatingRow.submitted_at.desc())))

def upsert_agent_configuration(s: Session, agent_id: str, key: str, value: str, source: Optional[str] = None, created_by: Optional[str] = None) -> AgentConfigurationRow:
    # We could implement versioning, but for now we simply update or create.
    row = s.scalars(select(AgentConfigurationRow).where(AgentConfigurationRow.agent_id == agent_id, AgentConfigurationRow.configuration_key == key)).first()
    if not row:
        row = AgentConfigurationRow(
            agent_id=agent_id,
            configuration_key=key,
            configuration_value=value,
            source=source,
            created_by=created_by,
            updated_by=created_by
        )
        s.add(row)
    else:
        row.configuration_value = value
        if source: row.source = source
        row.updated_by = created_by
        row.updated_at = _utcnow()
        row.version += 1
    s.flush()
    return row

def list_agent_configurations(s: Session, agent_id: str) -> list[AgentConfigurationRow]:
    return list(s.scalars(select(AgentConfigurationRow).where(AgentConfigurationRow.agent_id == agent_id)))

def upsert_agent_kra(s: Session, agent_id: str, kra_name: str, target_value: float, weight: float) -> AgentKRARow:
    row = s.scalars(select(AgentKRARow).where(AgentKRARow.agent_id == agent_id, AgentKRARow.kra_name == kra_name)).first()
    if not row:
        row = AgentKRARow(
            agent_id=agent_id,
            kra_name=kra_name,
            target=str(target_value),
            weight=weight
        )
        s.add(row)
    else:
        row.target = str(target_value)
        row.weight = weight
    s.flush()
    return row

def list_agent_kras(s: Session, agent_id: str) -> list[AgentKRARow]:
    return list(s.scalars(select(AgentKRARow).where(AgentKRARow.agent_id == agent_id)))

def update_agent_status(s: Session, agent_id: str, status: str) -> AgentRow:
    agent = s.scalars(select(AgentRow).where(AgentRow.id == agent_id)).first()
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    agent.status = status
    agent.last_seen = _utcnow()
    s.flush()
    return agent
