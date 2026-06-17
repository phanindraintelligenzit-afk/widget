"""Source-specific adapters — one per source system, each owning a
narrow slice of the canonical contract.
"""
from .arize import ArizeAdapter
from .aws_cost import AwsCostAdapter
from .base import SourceAdapter
from .jira import JiraAdapter
from .puvi_noise import PuviNoiseAdapter
from .ray import RayAdapter
from .servicenow import ServiceNowAdapter
from .bmc import BmcAdapter
from .bedrock import BedrockAdapter
from .sap_hr import SapHrAdapter
from .langgraph import LangGraphAdapter
from .audit_trail import AuditTrailAdapter
from .langsmith import LangSmithAdapter
from .braintrust import BraintrustAdapter
from .galileo import GalileoAdapter
from .opik import OpikAdapter
from .langfuse import LangfuseAdapter
from .agentops import AgentOpsAdapter
from .openllmetry import OpenLLMetryAdapter
from .mlflow import MlflowAdapter
from .registry import clear, get, list_sources, register
from .stubs import (
    ALL_STUBS,
)

REAL_ADAPTERS = (
    AwsCostAdapter,
    PuviNoiseAdapter,
    ArizeAdapter,
    JiraAdapter,
    RayAdapter,
    ServiceNowAdapter,
    BmcAdapter,
    BedrockAdapter,
    SapHrAdapter,
    LangGraphAdapter,
    AuditTrailAdapter,
    LangSmithAdapter,
    BraintrustAdapter,
    GalileoAdapter,
    OpikAdapter,
    LangfuseAdapter,
    AgentOpsAdapter,
    OpenLLMetryAdapter,
    MlflowAdapter,
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
    "LangSmithAdapter",
    "BraintrustAdapter",
    "GalileoAdapter",
    "OpikAdapter",
    "LangfuseAdapter",
    "AgentOpsAdapter",
    "OpenLLMetryAdapter",
    "MlflowAdapter",
    "clear",
    "get",
    "list_sources",
    "register",
    "register_all",
]
