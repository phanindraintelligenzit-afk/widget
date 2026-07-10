"""Adapter contract.

An adapter translates one source (an agent runtime, an observability tool,
an ITSM system) into one or more canonical AgentObservation objects. That
is its only job. Adapters import contract; engine never imports adapters.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from contract import AgentObservation


class Adapter(ABC):
    """Implement `to_observations()`. Set a unique `name` for the registry."""

    name: str = ""

    @abstractmethod
    def to_observations(self, payload: Any) -> list[AgentObservation]:
        ...
