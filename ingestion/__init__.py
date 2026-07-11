"""Ingestion layer: adapters + registry. The engine never imports from here.

Two adapter families:
    Adapter        → produces full AgentObservation. Registered in `registry`.
                     Routed by /ingest/{name}.
    SourceAdapter  → produces PartialObservation (one dimension's worth).
                     Registered in `sources.registry`. Routed by
                     /ingest/source/{name}.
"""
from . import sources
from .base import Adapter
from .generic import FieldMapping, GenericWebhookAdapter
from .registry import clear, get, list_adapters, register
from .sources import SourceAdapter

__all__ = [
    "Adapter",
    "FieldMapping",
    "GenericWebhookAdapter",
    "SourceAdapter",
    "clear",
    "get",
    "list_adapters",
    "register",
    "sources",
]
