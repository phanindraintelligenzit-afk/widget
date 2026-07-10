"""Fallback patcher for unrecognized agent objects.

The user passed in something that doesn't look like any of the
supported frameworks. We try our best: search for any callable named
``invoke``, ``run``, ``kickoff``, ``call``, or ``__call__`` and treat
each invocation as a "run". We also surface a one-time log message
that names the actual class so the user can file a feature request
for native support.

Collector resolution strategy:
  1. Check ``dpi_ls._state.get_collector()`` first — this is the "current"
     collector, so a second ``monitor()`` call (which resets the state)
     automatically wins.
  2. Fall back to the closure-captured collector reference. This ensures
     that tests which call ``detect_and_install(obj, c)`` directly —
     without going through ``monitor()`` — still work correctly.

Re-install idempotency: if the wrapper already exists on the agent we
update the shared collector reference stored on the agent. This handles
the pattern ``detect_and_install(obj, c1); detect_and_install(obj, c2);
obj.invoke()`` — the second collector wins.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from .. import _state
from ..collector import SignalCollector
from .base import BasePatcher, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.unknown")

# Method names we treat as "run" entry points. Order matters only
# for the order we check — first match wins.
#
# `query` / `aquery` cover frameworks that use "query" as the run verb:
#   * Haystack pipelines: `pipeline.run()`, but query-shaped components
#     like `Retriever.retrieve()` are wrapped by the RAGPatcher.
#   * Google Vertex AI Agent Engine: `agent.query()` / `agent.stream_query()`.
#   * Elasticsearch / OpenSearch clients (when used as agents).
#   * Anything else that picked the SQL-flavoured name for "ask the agent".
_CANDIDATE_METHODS: tuple[str, ...] = (
    "invoke", "ainvoke", "run", "arun", "kickoff", "akickoff", "call", "__call__",
    "query", "aquery",
)

# Attribute we attach to the agent instance to share the mutable
# collector reference between the wrappers and future re-installs.
_COLLECTOR_REF_ATTR = "_dpi_ls_collector_ref"

_warned: set[int] = set()  # de-dupe the "unrecognized" warning per type


class UnknownPatcher(BasePatcher):
    name = "unknown"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        cls = type(agent)
        if id(cls) not in _warned:
            _warned.add(id(cls))
            _log.info(
                "dpi_ls.monitor() didn't recognise %s.%s. "
                "Best-effort instrumentation is in place — outputs and "
                "errors will be captured, but per-LLM token counts won't. "
                "Open an issue with the framework name for native support.",
                cls.__module__, cls.__name__,
            )

        # Get or create the shared mutable collector reference for this
        # agent instance. On a second install() call we just update the
        # existing reference so the already-installed wrappers pick up
        # the new collector on the next invocation.
        existing_ref = getattr(agent, _COLLECTOR_REF_ATTR, None)
        if existing_ref is not None:
            existing_ref[0] = collector
            _log.debug("Updated collector reference on already-patched agent.")
            return []  # wrappers already installed; nothing new to patch

        collector_ref: list[SignalCollector] = [collector]
        try:
            object.__setattr__(agent, _COLLECTOR_REF_ATTR, collector_ref)
        except (AttributeError, TypeError):
            # Some objects don't allow arbitrary attribute setting. Fall back
            # to storing the ref on the class (less ideal but still works).
            try:
                setattr(type(agent), _COLLECTOR_REF_ATTR, collector_ref)
            except (AttributeError, TypeError):
                pass

        patched: list[str] = []
        for name in _CANDIDATE_METHODS:
            original = getattr(agent, name, None)
            if original is None or already_patched(original):
                continue
            wrapped = _wrap_unknown(original, collector_ref)
            try:
                setattr(agent, name, wrapped)
                mark_patched(wrapped)
                patched.append(name)
            except (AttributeError, TypeError):
                continue
        if patched:
            _log.debug("Best-effort patched unknown agent: %s", patched)
        return patched


def _wrap_unknown(original, collector_ref: list):
    """Build a wrapper that delegates to ``original`` and writes to the
    currently-active collector.

    Resolution order:
    1. ``_state.get_collector()`` — wins when ``monitor()`` set the state
       (handles multi-monitor scenarios where the second call takes over).
    2. ``collector_ref[0]`` — fallback for tests that call
       ``detect_and_install()`` directly without going through ``monitor()``.
    """
    import inspect
    is_coro = inspect.iscoroutinefunction(original)

    if is_coro:
        async def async_wrapper(*args, **kwargs):
            collector = _state.get_collector() or collector_ref[0]
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="unknown")
                raise
            _capture(collector, result)
            return result
        return functools.wraps(original)(async_wrapper)

    def sync_wrapper(*args, **kwargs):
        collector = _state.get_collector() or collector_ref[0]
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="unknown")
            raise
        _capture(collector, result)
        return result
    return functools.wraps(original)(sync_wrapper)


def _capture(collector: SignalCollector, result: Any) -> None:
    """Record a successful invocation without double-counting attempts.

    The wrapper already called ``record_error`` on failure (which bumps
    attempts + failed). For successes we call ``record_llm_call`` which
    handles attempts, successful, output capture, and policy/validation
    checks all in one place — the wrapper must NOT pre-increment before
    calling here.
    """
    text = _safe_text(result)
    if text:
        # record_llm_call bumps attempts + successful and captures output.
        collector.record_llm_call(text, ok=True)
    else:
        # No text output — still count the execution.
        collector.record_llm_call("", ok=True)
