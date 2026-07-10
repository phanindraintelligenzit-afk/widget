"""Adapter registry — onboarding a new source = registering an adapter."""
from __future__ import annotations

from .base import Adapter

_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter, *, replace: bool = False) -> None:
    if not adapter.name:
        raise ValueError("Adapter must declare a non-empty `name`.")
    if adapter.name in _REGISTRY and not replace:
        raise ValueError(
            f"Adapter '{adapter.name}' is already registered. "
            "Pass replace=True to override."
        )
    _REGISTRY[adapter.name] = adapter


def get(name: str) -> Adapter:
    if name not in _REGISTRY:
        raise KeyError(
            f"No adapter registered for source '{name}'. "
            f"Known: {sorted(_REGISTRY) or '(none)'}"
        )
    return _REGISTRY[name]


def list_adapters() -> list[str]:
    return sorted(_REGISTRY)


def clear() -> None:
    """Test helper. Not for production."""
    _REGISTRY.clear()
