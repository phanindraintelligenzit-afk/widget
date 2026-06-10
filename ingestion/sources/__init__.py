"""Source-specific adapters — one per source system, each owning a
narrow slice of the canonical contract.
"""
from .arize import ArizeAdapter
from .aws_cost import AwsCostAdapter
from .base import SourceAdapter
from .jira import JiraAdapter
from .puvi_noise import PuviNoiseAdapter
from .ray import RayAdapter
from .audit_trail import AuditTrailAdapter
from .registry import clear, get, list_sources, register
from .stubs import (
    ALL_STUBS,
    BedrockAdapter,
    BmcAdapter,
    LangGraphAdapter,
    SapHrAdapter,
)

REAL_ADAPTERS = (
    AwsCostAdapter,
    PuviNoiseAdapter,
    ArizeAdapter,
    JiraAdapter,
    RayAdapter,
    AuditTrailAdapter,
)


def register_all() -> None:
    """Register every source adapter (real + stub). Idempotent."""
    for cls in (*REAL_ADAPTERS, *ALL_STUBS):
        if cls().name not in list_sources():
            register(cls())


__all__ = [
    "ALL_STUBS",
    "ArizeAdapter",
    "AwsCostAdapter",
    "BedrockAdapter",
    "BmcAdapter",
    "JiraAdapter",
    "LangGraphAdapter",
    "PuviNoiseAdapter",
    "RayAdapter",
    "REAL_ADAPTERS",
    "SapHrAdapter",
    "SourceAdapter",
    "clear",
    "get",
    "list_sources",
    "register",
    "register_all",
]
