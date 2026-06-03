"""Ingestion layer: adapters + registry. The engine never imports from here."""
from .base import Adapter
from .generic import FieldMapping, GenericWebhookAdapter, OTelAdapter
from .registry import clear, get, list_adapters, register

__all__ = [
    "Adapter",
    "FieldMapping",
    "GenericWebhookAdapter",
    "OTelAdapter",
    "clear",
    "get",
    "list_adapters",
    "register",
]
