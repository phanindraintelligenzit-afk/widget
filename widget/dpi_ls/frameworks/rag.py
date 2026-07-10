"""General RAG patcher.

A "RAG pattern" agent is anything whose primary job is:

    user query  →  retrieve relevant documents  →  synthesise an answer

The retrieval step is the distinguishing feature — it shows up in the
dashboard as a separate count (drives E, captured by V / G for policy
scanning, kept OUT of the Q evaluator's input because raw corpus text
would drown the LLM in noise).

Two shapes trigger the RAGPatcher:

1. **The user passed a retriever directly** — e.g.
   ``dpi_ls.monitor(vectorstore.as_retriever(), ...)``. We wrap the
   retriever's ``retrieve`` / ``aretrieve`` /
   ``get_relevant_documents`` methods.

2. **The dispatcher routed a chain here** because it has a
   ``.retriever`` attribute. In this case the chain's own ``invoke``
   is an AGENT RUN (it returns a synthesised answer), not a
   retrieval — wrapping it as a retrieval would double-count. So we
   wrap ONLY the nested retriever's methods and leave the chain's
   own entry point untouched (the UnknownPatcher fallback covers
   ``invoke`` / ``run``).

The wrapper follows the same idempotent ``_PATCHED_FLAG`` pattern as
the framework-specific patchers, uses the shared collector-swap-on-
reinstall mechanism in ``base.py``, and uses ``object.__setattr__`` to
bypass Pydantic v2's frozen-model guard.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from ..collector import SignalCollector
from .base import (
    BasePatcher,
    already_patched,
    attach_collector_ref,
    mark_patched,
    resolve_collector,
)
from .llama_index import _summarise_nodes

_log = logging.getLogger("dpi_ls.frameworks.rag")

# Method names we treat as retrieval entry points on a retriever-shaped
# object. We do NOT include ``invoke`` / ``ainvoke`` here because those
# are agent-run entry points on a chain — the dispatcher routes
# chain-with-retriever to RAGPatcher specifically so the NESTED
# retriever is wrapped, while the chain's own invoke/run falls through
# to UnknownPatcher.
_RETRIEVE_METHODS: tuple[str, ...] = (
    "retrieve",
    "aretrieve",
    "get_relevant_documents",
    "aget_relevant_documents",
)


def _is_retriever_shaped(obj: Any) -> bool:
    """True if ``obj`` itself exposes a retriever entry point.

    We treat an object as a retriever (not a chain) if it has at least
    one of the standard retrieval methods. The dispatcher may route
    chain-shaped objects here (those with a ``.retriever`` attribute)
    — those are handled differently in ``RAGPatcher.install``.
    """
    return any(callable(getattr(obj, m, None)) for m in _RETRIEVE_METHODS)


class RAGPatcher(BasePatcher):
    """Best-effort instrumentation for retriever-shaped objects.

    This patcher is also the fallback the dispatcher routes to when
    an object isn't recognised by any of the framework-specific
    patchers AND has a ``.retriever`` attribute. See
    ``frameworks/__init__.py:detect_framework``.
    """
    name = "rag"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        # Attach (or update) the mutable collector reference on the
        # primary agent AND on any nested retriever, so a re-install
        # with a different collector takes effect immediately.
        attach_collector_ref(agent, collector)

        patched: list[str] = []
        if _is_retriever_shaped(agent):
            # Case 1: the user passed a retriever directly. Wrap its
            # retrieval methods.
            for attr in _RETRIEVE_METHODS:
                patched.extend(_try_wrap(agent, attr))
        # Case 2: a chain with a nested retriever (LangChain RetrievalQA
        # etc.) — wrap the NESTED retriever's methods, leave the chain's
        # own invoke/run untouched so the UnknownPatcher fallback
        # handles it as a normal agent run.
        retriever = getattr(agent, "retriever", None)
        if retriever is not None and retriever is not agent:
            attach_collector_ref(retriever, collector)
            for attr in _RETRIEVE_METHODS:
                patched.extend(_try_wrap(retriever, attr, prefix="retriever."))
        if patched:
            _log.debug("Patched RAG object: %s", patched)
        return patched


def _try_wrap(
    owner: Any,
    attr: str,
    prefix: str = "",
) -> list[str]:
    """Wrap ``owner.attr`` if it exists and isn't already patched."""
    original = getattr(owner, attr, None)
    if original is None or already_patched(original):
        return []
    if not callable(original):
        return []
    wrapped = _wrap_retrieve(original, owner, attr)
    label = f"{prefix}{attr}"
    try:
        setattr(owner, attr, wrapped)
        mark_patched(wrapped)
        return [label]
    except (AttributeError, TypeError, ValueError):
        try:
            object.__setattr__(owner, attr, wrapped)
            mark_patched(wrapped)
            _log.debug("Patched %s via object.__setattr__ (Pydantic v2 model).", label)
            return [label]
        except Exception as inner:  # pragma: no cover - truly frozen
            _log.debug("Could not patch %s (read-only): %s", label, inner)
            return []


def _wrap_retrieve(original, owner: Any, attr: str):
    """Wrap a retrieve / get_relevant_documents method.

    The wrapped call records one retrieval (drives E) and captures the
    returned node texts as ``_KIND_TOOL`` outputs so V / G see them
    but the Q evaluator does not.

    The collector is resolved on every call via ``resolve_collector``
    so a re-install with a different collector takes effect
    immediately.
    """
    import inspect
    is_async = inspect.iscoroutinefunction(original) or attr.startswith("a")

    if is_async:
        async def async_wrapper(*args, **kwargs):
            collector = resolve_collector(owner, fallback=None)
            if collector is None:
                return await original(*args, **kwargs)
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="rag")
                raise
            _capture_retrieval(collector, result)
            return result
        return functools.wraps(original)(async_wrapper)

    def sync_wrapper(*args, **kwargs):
        collector = resolve_collector(owner, fallback=None)
        if collector is None:
            return original(*args, **kwargs)
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="rag")
            raise
        _capture_retrieval(collector, result)
        return result
    return functools.wraps(original)(sync_wrapper)


def _capture_retrieval(collector: SignalCollector, result: Any) -> None:
    """Count the retrieval and capture node snippets as 'tool' outputs.

    The summary helper is shared with the LlamaIndex patcher since
    retrievers in both ecosystems return the same shape
    (``list[NodeWithScore]`` / ``list[Document]`` / ``list[str]``).
    """
    docs_count, top_score, snippets = _summarise_nodes(result)
    collector.record_retrieval(docs_count=docs_count, top_score=top_score)
    for snippet in snippets[:4]:
        if snippet:
            collector._capture_output(snippet, kind="tool")
