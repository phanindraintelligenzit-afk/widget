"""Orchestration: observation -> metrics -> Rating -> persist.

The API layer's only job between request and DB. The engine stays pure
and only sees normalized metrics; this module is where settings + DB
meet the engine.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from contract import AgentBaseline, AgentObservation, PartialObservation, Rating, merge_partials
from engine import metrics_from_observation, metrics_from_partial, rate
from store import repo


def score_and_persist(
    s: Session,
    obs: AgentObservation,
    *,
    baseline: Optional[float] = None,
) -> Rating:
    settings = repo.get_settings(s)
    agent = repo.upsert_agent(s, obs.agent_id, obs.agent_name, baseline=baseline)
    baseline_obj = AgentBaseline(
        agent_id=obs.agent_id,
        human_output_per_period=agent.baseline_human_output,
    )
    metrics = metrics_from_observation(obs, settings, baseline_obj)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )
    obs_row = repo.save_observation(s, obs)
    repo.save_score(s, obs.agent_id, obs_row.id, rating)
    return rating


def rescore_from_partials(s: Session, agent_id: str) -> Rating | None:
    """Re-merge every stored partial for this agent and rate the result.

    Returns None if the agent has no partials. Persists the score linked
    to the most recent partial's id so history stays causal.
    """
    partials = repo.partials_for_agent(s, agent_id)
    if not partials:
        return None

    merged = merge_partials(partials)
    settings = repo.get_settings(s)
    agent = repo.upsert_agent(s, merged.agent_id, merged.agent_name or merged.agent_id)
    baseline = AgentBaseline(
        agent_id=merged.agent_id,
        human_output_per_period=agent.baseline_human_output,
    )
    metrics = metrics_from_partial(merged, settings, baseline)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
        min_dimensions_for_full_band=settings.min_dimensions_for_full_band,
    )

    # Link the score to the most recent partial — gives history a sensible
    # causal anchor even though the score is from the merged set.
    from store.models import PartialObservationRow
    from sqlalchemy import select
    most_recent_id = s.scalar(
        select(PartialObservationRow.id)
        .where(PartialObservationRow.agent_id == agent_id)
        .order_by(PartialObservationRow.received_at.desc(), PartialObservationRow.id.desc())
        .limit(1)
    )
    repo.save_score(s, agent_id, most_recent_id, rating)
    return rating


def ingest_partials(s: Session, partials: list[PartialObservation]) -> list[Rating]:
    """Persist each partial, then re-score every distinct agent touched."""
    affected: set[str] = set()
    for p in partials:
        repo.upsert_agent(s, p.agent_id, p.agent_name or p.agent_id)
        repo.save_partial(s, p)
        affected.add(p.agent_id)
    out: list[Rating] = []
    for agent_id in sorted(affected):
        r = rescore_from_partials(s, agent_id)
        if r is not None:
            out.append(r)
    return out
