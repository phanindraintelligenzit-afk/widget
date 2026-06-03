"""Orchestration: AgentObservation -> metrics -> Rating -> persist.

The API layer's only job between request and DB. The engine stays pure
and only sees normalized metrics; this module is where settings + DB
meet the engine.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from contract import AgentBaseline, AgentObservation, Rating
from engine import metrics_from_observation, rate
from store import repo


def score_and_persist(s: Session, obs: AgentObservation) -> Rating:
    settings = repo.get_settings(s)
    agent = repo.upsert_agent(s, obs.agent_id, obs.agent_name)
    baseline = AgentBaseline(
        agent_id=obs.agent_id,
        human_output_per_period=agent.baseline_human_output,
    )
    metrics = metrics_from_observation(obs, settings, baseline)
    rating = rate(
        metrics,
        weights=settings.weights,
        gate_thresholds=settings.gate_thresholds,
    )
    obs_row = repo.save_observation(s, obs)
    repo.save_score(s, obs.agent_id, obs_row.id, rating)
    return rating
