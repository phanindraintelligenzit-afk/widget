"""LangGraph patcher.

A compiled LangGraph (``CompiledStateGraph``) is the user's "agent".
The two entry points are ``invoke`` (sync) and ``ainvoke`` (async). We
wrap both so the collector observes one run per call.

The trick is that LangGraph's ainvoke yields the final state, not the
LLM call, so we don't get per-token granularity out of the box. We
record the final state as one "output" — good enough for the Q eval
which only needs samples of agent output.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from ..collector import SignalCollector
from .base import BasePatcher, _extract_input_text, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.langgraph")


class LangGraphPatcher(BasePatcher):
    name = "langgraph"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        patched: list[str] = []
        for attr in ("invoke", "ainvoke"):
            original = getattr(agent, attr, None)
            if original is None or already_patched(original):
                continue
            wrapped = _wrap_invoke(original, collector, attr)
            try:
                setattr(agent, attr, wrapped)
                mark_patched(wrapped)
                patched.append(f"graph.{attr}")
            except (AttributeError, TypeError):
                # Some compiled graphs are read-only; we can't patch.
                _log.debug("Could not patch graph.%s (read-only).", attr)
        if patched:
            _log.debug("Patched LangGraph graph: %s", patched)
        return patched


def _wrap_invoke(original, collector: SignalCollector, attr: str):
    import inspect

    if attr == "ainvoke":
        if not inspect.iscoroutinefunction(original):
            # Some graphs expose ainvoke as a coroutine returning method.
            pass

        async def async_wrapper(*args, **kwargs):
            # Auto-record the graph input as source data for hallucination eval.
            input_text = _extract_input_text(args, kwargs)
            if input_text:
                collector.record_source(input_text, kind="input")
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="langgraph")
                raise
            _capture_graph_result(collector, result)
            return result
        return functools.wraps(original)(async_wrapper)

    def sync_wrapper(*args, **kwargs):
        # Auto-record the graph input as source data for hallucination eval.
        input_text = _extract_input_text(args, kwargs)
        if input_text:
            collector.record_source(input_text, kind="input")
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="langgraph")
            raise
        _capture_graph_result(collector, result)
        return result
    return functools.wraps(original)(sync_wrapper)


def _capture_graph_result(collector: SignalCollector, result: Any) -> None:

    """Extract the agent's final text from a LangGraph final state.

    Instead of trying to find a specific key, we serialize the entire 
    final state dictionary so the Q evaluator can assess the entire 
    agent output.
    """
    text = _safe_text(result)
    if text:
        collector.record_llm_call(text, ok=True, action_name="langgraph_invoke")
    else:
        # We got an empty response but the run completed without raising.
        # Record it so the execution attempt matches the agent run.
        collector.record_llm_call("", ok=True, action_name="langgraph_invoke")
