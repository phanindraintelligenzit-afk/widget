"""Framework-specific patchers, plus the dispatcher.

The public surface is :func:`detect_and_install` — given a user-supplied
``agent`` object and a collector, it picks the right patcher and wires
it up. Detection is by module + class shape, not by isinstance checks
against concrete classes, so we don't import a framework's package just
to ask ``isinstance(x, TheirClass)``.
"""
from __future__ import annotations

import logging
from typing import Any

from ..collector import SignalCollector
from .autogen import AutoGenPatcher
from .base import BasePatcher
from .crewai import CrewAIPatcher
from .langchain import LangChainPatcher
from .langgraph import LangGraphPatcher
from .openai_agents import OpenAIAgentsPatcher
from .raw_anthropic import RawAnthropicPatcher
from .raw_openai import RawOpenAIPatcher
from .unknown import UnknownPatcher

_log = logging.getLogger("dpi_ls.frameworks")


def detect_framework(agent: Any) -> BasePatcher:
    """Return the patcher that best matches ``agent``.

    Order matters: more specific detectors run first. The OpenAI Agents
    SDK is checked before the raw OpenAI client because both share the
    ``openai`` module name (the SDK lives in a top-level ``agents``
    package but the raw client lives in ``openai``).
    """
    cls = type(agent)
    module = (cls.__module__ or "").lower()
    qualname = (getattr(cls, "__qualname__", "") or "").lower()

    # 1. OpenAI Agents SDK — top-level ``agents`` package, has
    #    ``.instructions`` and ``.tools`` attributes. The Agent class
    #    itself is in the ``agents`` module, not the ``openai`` one.
    if module.startswith("agents"):
        return OpenAIAgentsPatcher()
    # 2. LangGraph — CompiledStateGraph classes live in langgraph.graph
    #    or langgraph.pregel.
    if module.startswith("langgraph"):
        return LangGraphPatcher()
    # 3. LangChain runnables — modules under langchain.* / langchain_core.
    if module.startswith("langchain") or "langchain_core" in module:
        return LangChainPatcher()
    # 4. CrewAI.
    if module.startswith("crewai"):
        return CrewAIPatcher()
    # 5. AutoGen — historically under pyautogen or autogen.
    if "autogen" in module:
        return AutoGenPatcher()
    # 6. Raw OpenAI client — openai.OpenAI / AsyncOpenAI.
    if module.startswith("openai") and hasattr(agent, "chat"):
        return RawOpenAIPatcher()
    # 7. Raw Anthropic client — anthropic.Anthropic / AsyncAnthropic.
    if module.startswith("anthropic") and hasattr(agent, "messages"):
        return RawAnthropicPatcher()
    # 8. Last resort — best-effort instrumentation.
    return UnknownPatcher()


def detect_and_install(agent: Any, collector: SignalCollector) -> list[str]:
    """Pick a patcher and install it. Return the list of patched paths."""
    patcher = detect_framework(agent)
    try:
        patched = patcher.install(agent, collector)
    except Exception as e:  # pragma: no cover - patchers must not crash
        _log.warning("Patcher %s raised during install: %s", patcher.name, e)
        return []
    if not patched:
        # Patcher found nothing to instrument — fall back to the
        # unknown patcher so we at least capture the next user call.
        if not isinstance(patcher, UnknownPatcher):
            _log.debug(
                "%s patcher found nothing to instrument; falling back to best-effort.",
                patcher.name,
            )
            patched = UnknownPatcher().install(agent, collector)
    return patched


__all__ = [
    "AutoGenPatcher",
    "BasePatcher",
    "CrewAIPatcher",
    "LangChainPatcher",
    "LangGraphPatcher",
    "OpenAIAgentsPatcher",
    "RawAnthropicPatcher",
    "RawOpenAIPatcher",
    "UnknownPatcher",
    "detect_and_install",
    "detect_framework",
]
