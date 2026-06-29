"""Source-specific adapters — one per source system, each owning a
narrow slice of the canonical contract.
"""
from .aws_cost import AwsCostAdapter
from .base import SourceAdapter
from .bedrock import BedrockAdapter
from .langfuse import LangfuseAdapter
from .prometheus import PrometheusAdapter
from .registry import clear, get, list_sources, register
from .stubs import (
    ALL_STUBS,
)

REAL_ADAPTERS = (
    AwsCostAdapter,
    BedrockAdapter,
    LangfuseAdapter,
    PrometheusAdapter,
)


def register_all() -> None:
    """Register every source adapter (real + stub). Idempotent."""
    for cls in (*REAL_ADAPTERS, *ALL_STUBS):
        if cls().name not in list_sources():
            register(cls())


__all__ = [
    "ALL_STUBS",
    "AwsCostAdapter",
    "BedrockAdapter",
    "LangfuseAdapter",
    "PrometheusAdapter",
    "REAL_ADAPTERS",
    "SourceAdapter",
    "clear",
    "get",
    "list_sources",
    "register",
    "register_all",
]
