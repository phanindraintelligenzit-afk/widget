"""LlamaIndex patcher.

LlamaIndex's primary run entry points live on three base classes:

* ``BaseQueryEngine``  →  ``query(str) -> Response`` / ``aquery(str) -> Response``
* ``BaseRetriever``    →  ``retrieve(str) -> List[NodeWithScore]`` /
                           ``aretrieve(str) -> List[NodeWithScore]``
* ``BaseChatEngine``   →  ``chat(str) -> AgentChatResponse`` /
                           ``achat(str) -> AgentChatResponse``

We wrap whatever exists on the user's object — the same object might be
a ``VectorStoreIndex`` (whose ``as_query_engine()`` returns a query
engine), a pre-built ``RetrieverQueryEngine`` (with its own retriever
attribute), or a low-level retriever.

Response handling
-----------------

* ``query`` / ``aquery``  — record as one **agent run** (P) plus one
  **LLM call** (drives E, V, G, Q). Token counts come from
  ``response.metadata['usage']`` (LlamaIndex stores them there) or
  ``response.raw['usage']`` (raw OpenAI-shape responses). The
  response text is captured as ``_KIND_AGENT`` so the Q LLM
  evaluator sees it.

* ``retrieve`` / ``aretrieve``  — record as one **retrieval** (drives
  E via ``record_retrieval``) and capture each retrieved node as
  ``_KIND_TOOL`` so the deterministic V and G scanners see the
  evidence but the Q LLM evaluator does NOT — a retriever
  returning raw corpus text would otherwise drown the evaluator in
  noise.

* ``chat`` / ``achat``  — same shape as ``query`` / ``aquery``.

The wrapper follows the same idempotent ``_PATCHED_FLAG`` pattern as
the other framework patchers, uses ``object.__setattr__`` to bypass
Pydantic v2's frozen-model guard (LlamaIndex objects are Pydantic
models), and supports collector-swap-on-reinstall via the shared
``_dpi_ls_collector_ref`` mechanism in ``base.py``.
"""
from __future__ import annotations

import functools
import inspect
import json
import logging
from typing import Any

from ..collector import SignalCollector
from .base import (
    BasePatcher,
    _safe_iter_tokens,
    _safe_text,
    already_patched,
    attach_collector_ref,
    mark_patched,
    resolve_collector,
)

_log = logging.getLogger("dpi_ls.frameworks.llama_index")

# Methods we know are "run entry points". We patch whatever the user's
# object actually exposes — there's no LlamaIndex class that has all of
# these.
_RUN_METHODS: tuple[str, ...] = ("query", "aquery", "chat", "achat")
_RETRIEVE_METHODS: tuple[str, ...] = ("retrieve", "aretrieve")


class LlamaIndexPatcher(BasePatcher):
    name = "llama_index"
    one_run = False  # a script may call .query() many times

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        # Attach (or update) the mutable collector reference. The
        # wrapper below reads from this on every call so a re-install
        # with a different collector takes effect immediately — same
        # semantics as the UnknownPatcher's collector_ref list.
        attach_collector_ref(agent, collector)

        patched: list[str] = []
        # Run-level entry points: query / aquery / chat / achat
        for attr in _RUN_METHODS:
            patched.extend(_try_wrap(agent, attr, _wrap_run))
        # Retrieval-level entry points: retrieve / aretrieve
        for attr in _RETRIEVE_METHODS:
            patched.extend(_try_wrap(agent, attr, _wrap_retrieve))
        # If the object carries a retriever, wrap its methods too so we
        # observe the sub-call when query() runs.
        retriever = getattr(agent, "retriever", None)
        if retriever is not None and retriever is not agent:
            attach_collector_ref(retriever, collector)
            for attr in _RETRIEVE_METHODS:
                patched.extend(_try_wrap(retriever, attr, _wrap_retrieve, prefix="retriever."))
                
        try:
            from llama_index.core.tools.types import BaseTool
            for attr in ("__call__", "call", "acall"):
                patched.extend(_try_wrap(BaseTool, attr, _wrap_tool, prefix="tool."))
        except ImportError:
            pass
            
        if patched:
            _log.debug("Patched LlamaIndex object: %s", patched)
        return patched


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------

def _try_wrap(
    owner: Any,
    attr: str,
    wrap_fn,
    prefix: str = "",
) -> list[str]:
    """Wrap ``owner.attr`` if it exists and isn't already patched.

    Pydantic v2 (LlamaIndex) raises ``ValueError`` on setattr for unknown
    fields, so fall back to ``object.__setattr__`` on the instance __dict__.
    """
    original = getattr(owner, attr, None)
    if original is None or already_patched(original):
        return []
    wrapped = wrap_fn(original, owner, attr)
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


def _wrap_run(original, owner: Any, attr: str):
    """Wrap a query / aquery / chat / achat method.

    The wrapper records one agent run (P) and one LLM call (E, V, G, Q).
    Token counts are pulled from the LlamaIndex response's metadata
    (preferred) or its raw sub-response.

    The collector is resolved on EVERY call via
    ``resolve_collector(owner, fallback)`` so a re-install with a
    different collector takes effect immediately.
    """
    is_async = attr.startswith("a")

    if is_async:
        async def async_wrapper(*args, **kwargs):
            collector = resolve_collector(owner, fallback=None)
            if collector is None:
                return await original(*args, **kwargs)
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="llama_index")
                raise
            _capture_run_result(collector, result, attr)
            return result
        return functools.wraps(original)(async_wrapper)

    def sync_wrapper(*args, **kwargs):
        collector = resolve_collector(owner, fallback=None)
        if collector is None:
            return original(*args, **kwargs)
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="llama_index")
            raise
        _capture_run_result(collector, result, attr)
        return result
    return functools.wraps(original)(sync_wrapper)


def _wrap_retrieve(original, owner: Any, attr: str):
    """Wrap a retrieve / aretrieve method.

    Records a retrieval (drives E) and captures each returned node as
    a 'tool' output so V and G see the evidence but Q does not.
    """
    is_async = attr.startswith("a")

    if is_async:
        async def async_wrapper(*args, **kwargs):
            collector = resolve_collector(owner, fallback=None)
            if collector is None:
                return await original(*args, **kwargs)
            try:
                nodes = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="llama_index")
                raise
            _capture_retrieval(collector, nodes)
            return nodes
        return functools.wraps(original)(async_wrapper)

    def sync_wrapper(*args, **kwargs):
        collector = resolve_collector(owner, fallback=None)
        if collector is None:
            return original(*args, **kwargs)
        try:
            nodes = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="llama_index")
            raise
        _capture_retrieval(collector, nodes)
        return nodes
    return functools.wraps(original)(sync_wrapper)


# ---------------------------------------------------------------------------
# Result capture
# ---------------------------------------------------------------------------

def _capture_run_result(collector: SignalCollector, result: Any, attr: str) -> None:
    """Pull text + token usage out of a query / chat response."""
    text = _extract_response_text(result)
    in_t, out_t = _extract_response_tokens(result)

    # Drive P. A query/chat is one logical "run" of the agent.
    collector.record_agent_run(ok=True)
    if text or in_t or out_t:
        cost = (in_t + out_t) * 0.000001  # $0.001 per 1k tokens blended
        collector.record_llm_call(
            text or "", tokens_in=in_t, tokens_out=out_t, cost=cost, ok=True,
        )
    else:
        # Query returned nothing readable — still count it as a successful
        # empty call so E reflects the work.
        collector.record_llm_call("", ok=True)


def _capture_retrieval(collector: SignalCollector, nodes: Any) -> None:
    """Pull node texts and a top score from a retrieval result."""
    docs_count, top_score, snippets = _summarise_nodes(nodes)
    collector.record_retrieval(docs_count=docs_count, top_score=top_score)
    # Capture each node's text as a 'tool' output so the deterministic
    # V / G scanners run against it but the Q LLM evaluator does not.
    # Cap at the first ~4 nodes — the policy regex hits the same rules
    # on each snippet and we don't need a 50-doc transcript.
    for snippet in snippets[:4]:
        if snippet:
            collector._capture_output(snippet, kind="tool")


def _extract_response_text(result: Any) -> str:
    """Best-effort text extraction from a LlamaIndex Response / AgentChatResponse.

    Response objects have a ``.response`` (the synthesized answer string),
    a ``.source_nodes`` (retrieved context), and a ``.metadata`` dict.
    AgentChatResponse has a ``.response`` string.
    """
    # AgentChatResponse and Response both expose ``.response`` as the answer.
    direct = getattr(result, "response", None)
    if isinstance(direct, str) and direct:
        return direct
    # Fall back to the base helper — handles dicts, AIMessage, etc.
    return _safe_text(result)


def _extract_response_tokens(result: Any) -> tuple[int, int]:
    """Pull (in, out) tokens from a LlamaIndex response.

    LlamaIndex stores them in three possible places; we try each in turn:

    1. ``result.metadata['usage']`` (OpenAI-shaped, sometimes populated
       by ``TokenCountingHandler`` callbacks)
    2. ``result.raw['usage']`` (raw OpenAI ChatCompletion response)
    3. Anything ``_safe_iter_tokens`` can read directly off ``result``
    """
    meta = getattr(result, "metadata", None)
    if isinstance(meta, dict):
        usage = meta.get("usage")
        in_t, out_t = _safe_iter_tokens({"usage": usage}) if usage else (0, 0)
        if in_t or out_t:
            return in_t, out_t
    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        return _safe_iter_tokens(raw)
    return _safe_iter_tokens(result)


def _summarise_nodes(nodes: Any) -> tuple[int, float, list[str]]:
    """Return (count, top_score, [text snippets]) from a retrieval result.

    Handles the three shapes a retriever might return:

    * ``list[NodeWithScore]``  — each has ``.node.text`` / ``.node.get_content()``
      and ``.score`` (or ``.node.score``).
    * ``list[Document]``       — each has ``.page_content`` (LangChain) or
      ``.text`` (LlamaIndex Document).
    * ``list[str]``            — already plain.
    * Anything else            — count is len(nodes) if it has __len__,
      otherwise 0; no snippets.
    """
    if nodes is None:
        return 0, 0.0, []
    if isinstance(nodes, str):
        # A retriever that returns a single string is unusual; treat it
        # as one "document".
        return 1, 0.0, [nodes]
    if not hasattr(nodes, "__iter__"):
        return 0, 0.0, []

    snippets: list[str] = []
    top_score = 0.0
    for n in nodes:
        # Score — try a few common locations
        score = getattr(n, "score", None)
        if score is None and getattr(n, "node", None) is not None:
            score = getattr(n.node, "score", None)
        try:
            if score is not None:
                top_score = max(top_score, float(score))
        except (TypeError, ValueError):
            pass

        # Text — try .node.get_content() / .node.text / .text / .page_content
        text = ""
        if hasattr(n, "node") and n.node is not None:
            getter = getattr(n.node, "get_content", None)
            text = getter() if callable(getter) else getattr(n.node, "text", "")
        if not text:
            text = getattr(n, "text", "") or getattr(n, "page_content", "")
        if not text and isinstance(n, dict):
            text = n.get("text") or n.get("page_content") or n.get("content") or ""
        if isinstance(text, list):
            text = "\n".join(str(part) for part in text)
        if not text:
            try:
                text = json.dumps(n, default=str)[:1000]
            except Exception:  # noqa: BLE001
                text = str(n)[:1000]
        snippets.append(text)

    return len(snippets), top_score, snippets

def _wrap_tool(original, collector_ref: SignalCollector | None, attr: str):
    is_async = attr == "acall"

    if is_async:
        async def async_call(self, *args, **kwargs):
            collector = resolve_collector(self, collector_ref)
            tool_name = getattr(self, "metadata", None)
            if tool_name: tool_name = getattr(tool_name, "name", "tool")
            else: tool_name = getattr(self, "name", "tool")
            
            tool_args = kwargs.copy()
            if args:
                if len(args) == 1 and isinstance(args[0], dict):
                    tool_args.update(args[0])
                else:
                    tool_args["__args"] = args

            if not collector:
                return await original(self, *args, **kwargs)
            try:
                result = await original(self, *args, **kwargs)
                collector.record_tool_call(ok=True, action_name=tool_name, tool_args=tool_args)
                return result
            except Exception as e:
                collector.record_error(e, source="llama_index")
                collector.record_tool_call(ok=False, action_name=tool_name, tool_args=tool_args)
                raise
        return functools.wraps(original)(async_call)
    else:
        def sync_call(self, *args, **kwargs):
            collector = resolve_collector(self, collector_ref)
            tool_name = getattr(self, "metadata", None)
            if tool_name: tool_name = getattr(tool_name, "name", "tool")
            else: tool_name = getattr(self, "name", "tool")
            
            tool_args = kwargs.copy()
            if args:
                if len(args) == 1 and isinstance(args[0], dict):
                    tool_args.update(args[0])
                else:
                    tool_args["__args"] = args

            if not collector:
                return original(self, *args, **kwargs)
            try:
                result = original(self, *args, **kwargs)
                collector.record_tool_call(ok=True, action_name=tool_name, tool_args=tool_args)
                return result
            except Exception as e:
                collector.record_error(e, source="llama_index")
                collector.record_tool_call(ok=False, action_name=tool_name, tool_args=tool_args)
                raise
        return functools.wraps(original)(sync_call)
