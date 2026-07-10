"""Universal fallback: any source that can POST JSON is supported with
zero custom code — bring a YAML mapping, get an AgentObservation.
"""
from __future__ import annotations

from typing import Any

from contract import AgentObservation

from ..base import Adapter
from .mapping import FieldMapping


class GenericWebhookAdapter(Adapter):
    """Bind a YAML field-mapping to the canonical contract.

    A single payload yields one observation; a list yields one per item.
    Override `name` to register multiple webhook adapters side-by-side
    (one per source schema).
    """

    name = "generic_webhook"

    def __init__(self, mapping: FieldMapping, *, name: str | None = None):
        self.mapping = mapping
        if name is not None:
            self.name = name

    def to_observations(self, payload: Any) -> list[AgentObservation]:
        if isinstance(payload, list):
            return [self.mapping.apply(p) for p in payload]
        return [self.mapping.apply(payload)]
