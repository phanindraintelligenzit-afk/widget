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
from .llama_index import LlamaIndexPatcher
from .openai_agents import OpenAIAgentsPatcher
from .rag import RAGPatcher
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
    # 6. LlamaIndex — top-level ``llama_index`` package, covers
    #    ``llama_index.core`` (query engines, retrievers, indexes) and
    #    the sub-packages ``llama_index.llms.*``, ``llama_index.embeddings.*``, etc.
    if module.startswith("llama_index"):
        return LlamaIndexPatcher()
    # 7. Raw OpenAI client — openai.OpenAI / AsyncOpenAI.
    if module.startswith("openai") and hasattr(agent, "chat"):
        return RawOpenAIPatcher()
    # 8. Raw Anthropic client — anthropic.Anthropic / AsyncAnthropic.
    if module.startswith("anthropic") and hasattr(agent, "messages"):
        return RawAnthropicPatcher()
    # 9. Generic RAG — any retriever-shaped object, or anything with a
    #    ``.retriever`` attribute. This covers LangChain RetrievalQA
    #    chains, custom RAG chains, and standalone retrievers passed
    #    directly to ``monitor()``. Runs BEFORE the unknown fallback
    #    so RAG agents get RAG-specific instrumentation (retrievals
    #    counted as tool calls) instead of the catch-all invoke/run wrap.
    if not isinstance(agent, type):
        if hasattr(agent, "retriever"):
            return RAGPatcher()
        # Standalone retriever — the user passed one directly. Detected
        # by the presence of one of the standard retrieval methods.
        from .rag import _is_retriever_shaped
        if _is_retriever_shaped(agent):
            return RAGPatcher()
    # 10. Last resort — best-effort instrumentation.
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
        # Skip this when the agent is already a RAGPatcher match (a
        # standalone retriever with no retrievable methods is a user
        # error and we don't want to second-guess the routing).
        if not isinstance(patcher, (UnknownPatcher, RAGPatcher)):
            _log.debug(
                "%s patcher found nothing to instrument; falling back to best-effort.",
                patcher.name,
            )
            patched = UnknownPatcher().install(agent, collector)
            
    # Always attempt to apply the global LangChain BaseTool hook.
    # This guarantees that dynamically instantiated LangChain tools (which are popular
    # across CrewAI, AutoGen, etc.) are always captured regardless of the primary framework.
    try:
        from .langchain import LangChainPatcher
        lc_patched = LangChainPatcher().install(None, collector)
        if lc_patched:
            patched.extend(lc_patched)
    except ImportError:
        pass
        
    return patched


__all__ = [
    "AutoGenPatcher",
    "BasePatcher",
    "CrewAIPatcher",
    "LangChainPatcher",
    "LangGraphPatcher",
    "LlamaIndexPatcher",
    "OpenAIAgentsPatcher",
    "RAGPatcher",
    "RawAnthropicPatcher",
    "RawOpenAIPatcher",
    "UnknownPatcher",
    "detect_and_install",
    "detect_framework",
]
