"""CrewAI patcher.

A ``Crew`` is the runnable unit (``Crew.kickoff()``). The kickoff
method returns a ``CrewOutput`` with a ``raw`` string of the final
output, and possibly ``tasks_output`` (a list of per-task results).

We wrap ``kickoff`` (sync) and ``akickoff`` (async) so the collector
sees one run per kickoff.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from ..collector import SignalCollector
from .base import BasePatcher, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.crewai")


class CrewAIPatcher(BasePatcher):
    name = "crewai"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        patched: list[str] = []
        for attr in ("kickoff", "akickoff"):
            original = getattr(agent, attr, None)
            if original is None or already_patched(original):
                continue
            wrapped = _wrap_kickoff(original, collector, attr)
            try:
                setattr(agent, attr, wrapped)
                mark_patched(wrapped)
                patched.append(f"crew.{attr}")
            except (AttributeError, TypeError):
                _log.debug("Could not patch Crew.%s (read-only).", attr)
        if patched:
            _log.debug("Patched CrewAI crew: %s", patched)
        return patched


def _wrap_kickoff(original, collector: SignalCollector, attr: str):
    is_async = attr == "akickoff"

    if is_async:
        async def async_kickoff(*args, **kwargs):
            collector.attempts += 1
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="crewai")
                raise
            _capture_crew_output(collector, result)
            return result
        return functools.wraps(original)(async_kickoff)

    def sync_kickoff(*args, **kwargs):
        collector.attempts += 1
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="crewai")
            raise
        _capture_crew_output(collector, result)
        return result
    return functools.wraps(original)(sync_kickoff)


def _capture_crew_output(collector: SignalCollector, result: Any) -> None:
    """Best-effort: take the final raw output, plus any per-task outputs."""
    if result is None:
        collector.successful += 1
        return

    text = getattr(result, "raw", None) or _safe_text(result)
    if text:
        collector.record_llm_call(text, ok=True)

    # Each task is one LLM call in the collector's eyes. Use the
    # ``tasks_output`` list if present.
    tasks = getattr(result, "tasks_output", None)
    if tasks:
        for t in tasks:
            out = getattr(t, "raw", None) or _safe_text(t)
            if out:
                collector.attempts += 1
                collector.successful += 1
                collector._capture_output(out)

    if not text and not tasks:
        collector.successful += 1
