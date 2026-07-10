"""Bridge between the pure SME state machine and persistence + scoring.

When the user commits at the review step, the captured triple lands in
sme_ratings (audit) and a Q-only PartialObservation is pushed through
the same ingest_partials() path the source adapters use — so it
re-merges with everything else and triggers a fresh score.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from contract import PartialObservation, Quality, Rating
from engine import sme_flow
from store import repo

from .scoring import ingest_partials


def _to_state(payload: dict) -> sme_flow.SMEFlowState:
    return sme_flow.SMEFlowState(**payload)


def _to_payload(state: sme_flow.SMEFlowState) -> dict:
    return asdict(state)


def start_session(s: Session, agent_id: str, submitted_by: str) -> tuple[str, sme_flow.SMEFlowState]:
    state = sme_flow.start(agent_id=agent_id, submitted_by=submitted_by)
    sid = uuid.uuid4().hex
    repo.upsert_agent(s, agent_id, agent_id)  # ensure FK target exists
    repo.create_sme_session(s, sid, agent_id, _to_payload(state))
    return sid, state


def advance_session(
    s: Session, session_id: str, response: str
) -> tuple[sme_flow.SMEFlowState, Rating | None]:
    row = repo.get_sme_session(s, session_id)
    if row is None:
        raise KeyError(f"session '{session_id}' not found")
    state = _to_state(dict(row.state))
    state = sme_flow.advance(state, response)
    repo.update_sme_session(s, session_id, _to_payload(state))

    rating: Rating | None = None
    if sme_flow.is_committed(state):
        rating = _commit(s, state)
    return state, rating


def _commit(s: Session, state: sme_flow.SMEFlowState) -> Rating:
    # 1. Audit: durable SME rating row.
    repo.save_sme_rating(
        s,
        agent_id=state.agent_id,
        accuracy=state.accuracy,
        consistency=state.consistency,
        hallucination_rate=state.hallucination_rate,
        submitted_by=state.submitted_by,
    )
    # 2. Score: a Q-only PartialObservation through the existing merger.
    now = datetime.now(timezone.utc)
    partial = PartialObservation(
        agent_id=state.agent_id,
        agent_name=None,
        period_start=now,
        period_end=now,
        source="sme",
        quality=Quality(
            accuracy=state.accuracy,
            consistency=state.consistency,
            hallucination_rate=state.hallucination_rate,
        ),
    )
    ratings = ingest_partials(s, [partial])
    if ratings:
        return ratings[0]

    # Defensive fallback: ingest_partials returned no ratings (edge case —
    # e.g. the agent was deleted between start and commit, or a flush issue).
    # The SME quality triple IS saved to sme_ratings above. Return a Q-only
    # rating so the caller gets a valid object rather than crashing.
    from engine import compute_Q, rate as _rate
    settings = repo.get_settings(s)
    q = compute_Q(
        state.accuracy,
        state.consistency,
        state.hallucination_rate,
        settings.q_sub_weights,
    )
    return _rate(
        {"P": None, "Q": q, "E": None, "G": None, "R": None, "V": None, "C": None},
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )