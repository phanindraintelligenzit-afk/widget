"""Partial observations — single-dimension snapshots from sources that
only know about C, or only about G, etc.

The canonical AgentObservation is the all-dimensions-known case. A
PartialObservation can carry as little as one dimension's data plus
agent_id. A merger combines the latest partial per dimension into a
working metrics dict for the engine.

Sources that already emit complete observations (an agent runtime, OTel
spans aggregated per agent) keep using AgentObservation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import Cost, Executions, Incident, Policy, Quality, TaskStats, Validation


class PartialObservation(BaseModel):
    """One source's contribution to an agent's snapshot.

    Every field except agent_id, source, and the period bounds is
    optional. Whatever a source can supply, it supplies; whatever it
    can't is left None and stays the engine's "needs other source"
    signal — never zero.
    """
    agent_id: str
    agent_name: Optional[str] = None
    period_start: datetime
    period_end: datetime
    source: str

    tasks: Optional[TaskStats] = None
    executions: Optional[Executions] = None
    policy: Optional[Policy] = None
    incidents: Optional[list[Incident]] = None
    quality: Optional[Quality] = None
    validation: Optional[Validation] = None
    cost: Optional[Cost] = None


def merge_partials(partials: list[PartialObservation]) -> PartialObservation:
    """Combine partials by dimension; later (= more recent) wins.

    `partials` must be in chronological order — repository queries that
    `ORDER BY received_at ASC` feed this directly. Returns a single
    PartialObservation; dimensions never supplied stay None.
    """
    if not partials:
        raise ValueError("merge_partials requires at least one partial")

    first = partials[0]
    merged = PartialObservation(
        agent_id=first.agent_id,
        agent_name=first.agent_name,
        period_start=first.period_start,
        period_end=first.period_end,
        source="merged",
    )

    for p in partials:
        if p.agent_name:
            merged.agent_name = p.agent_name
        if p.period_start and p.period_start < merged.period_start:
            merged.period_start = p.period_start
        if p.period_end and p.period_end > merged.period_end:
            merged.period_end = p.period_end
        for field in ("tasks", "executions", "policy", "incidents",
                      "quality", "validation", "cost"):
            v = getattr(p, field)
            if v is not None:
                setattr(merged, field, v)

    return merged
