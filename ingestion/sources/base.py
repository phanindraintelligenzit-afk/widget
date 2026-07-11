"""Source-specific adapter contract.

Where a regular Adapter returns a complete AgentObservation (from a
source that knows the whole picture — an agent runtime, OTel spans),
a SourceAdapter returns one or more PartialObservation snapshots —
each carrying only the dimensions it can speak to.

Examples:
    aws_cost    → cost.ai_cost_per_output (drives C)
    puvi_noise  → policy.violations       (drives G)
    arize       → policy.violations + quality (drives G, sometimes Q)
    servicenow  → incidents               (drives R)
    jira        → incidents               (drives R)

The API merges per-agent partials by latest-wins-per-dimension before
scoring. Source-specific adapters never invent data for dimensions
they don't observe — that's how a fresh agent with just an AWS Cost
report still gets a defensible C-dominated score (engine redistributes
weight away from None metrics) instead of zero-pulled-everything-down.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from contract import PartialObservation


class SourceAdapter(ABC):
    """Implement `to_partials()`. Set a unique `name`."""

    name: str = ""

    @abstractmethod
    def to_partials(self, payload: Any) -> list[PartialObservation]:
        ...
