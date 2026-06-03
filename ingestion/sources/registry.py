"""Parallel registry for SourceAdapters. Separate from the
full-observation registry so the API routing stays unambiguous:
    POST /ingest/{name}         → Adapter             (full observation)
    POST /ingest/source/{name}  → SourceAdapter       (partial observation)
"""
from __future__ import annotations

from .base import SourceAdapter

_REGISTRY: dict[str, SourceAdapter] = {}


def register(adapter: SourceAdapter, *, replace: bool = False) -> None:
    if not adapter.name:
        raise ValueError("SourceAdapter must declare a non-empty `name`.")
    if adapter.name in _REGISTRY and not replace:
        raise ValueError(
            f"SourceAdapter '{adapter.name}' is already registered. "
            "Pass replace=True to override."
        )
    _REGISTRY[adapter.name] = adapter


def get(name: str) -> SourceAdapter:
    if name not in _REGISTRY:
        raise KeyError(
            f"No source adapter registered for '{name}'. "
            f"Known: {sorted(_REGISTRY) or '(none)'}"
        )
    return _REGISTRY[name]


def list_sources() -> list[str]:
    return sorted(_REGISTRY)


def clear() -> None:
    _REGISTRY.clear()
