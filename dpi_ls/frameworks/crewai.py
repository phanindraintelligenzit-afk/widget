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
from .base import BasePatcher, _extract_input_text, _safe_text, already_patched, mark_patched

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
            # ``Crew`` is a Pydantic v2 model and raises ``ValueError`` on
            # setattr for unknown fields, not the older ``AttributeError`` /
            # ``TypeError``. Catch all three so a frozen model doesn't kill
            # the whole patcher install.
            except (AttributeError, TypeError, ValueError):
                # Bypass the Pydantic validator by writing onto the instance
                # __dict__ directly. Pydantic v2 only intercepts __setattr__;
                # ``object.__setattr__`` is untouched and still works on
                # frozen / extra-forbidden models.
                try:
                    object.__setattr__(agent, attr, wrapped)
                    mark_patched(wrapped)
                    patched.append(f"crew.{attr}")
                    _log.debug(
                        "Patched Crew.%s via object.__setattr__ (Pydantic v2 model).",
                        attr,
                    )
                except Exception as inner:  # pragma: no cover - truly frozen
                    _log.debug(
                        "Could not patch Crew.%s (read-only, even via __dict__): %s",
                        attr, inner,
                    )
                    
        try:
            from crewai.tools.base_tool import BaseTool
            from .base import _try_wrap
            for attr in ("run", "_run", "execute", "invoke"):
                patched.extend(_try_wrap(BaseTool, attr, _wrap_tool, prefix="tool."))
        except ImportError:
            pass
            
        if patched:
            _log.debug("Patched CrewAI crew: %s", patched)
        return patched


def _wrap_kickoff(original, collector: SignalCollector, attr: str):
    is_async = attr == "akickoff"

    if is_async:
        async def async_kickoff(*args, **kwargs):
            input_text = _extract_input_text(args, kwargs)
            if input_text:
                collector.record_source(input_text, kind="input")
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="crewai")
                raise
            _capture_crew_output(collector, result, user_input=input_text)
            return result
        return functools.wraps(original)(async_kickoff)

    def sync_kickoff(*args, **kwargs):
        input_text = _extract_input_text(args, kwargs)
        if input_text:
            collector.record_source(input_text, kind="input")
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="crewai")
            raise
        _capture_crew_output(collector, result, user_input=input_text)
        return result
    return functools.wraps(original)(sync_kickoff)


def _capture_crew_output(collector: SignalCollector, result: Any, user_input: str | None = None) -> None:
    """Best-effort: take the final raw output, plus any per-task outputs."""
    if result is None:
        # The kickoff returned nothing — count as a successful empty call
        # so E is non-zero.
        collector.record_llm_call("", ok=True, user_input=user_input)
        return

    text = getattr(result, "raw", None) or _safe_text(result)
    if text:
        collector.record_llm_call(text, ok=True, user_input=user_input)

    # Each task is one LLM call in the collector's eyes. Use the
    # ``tasks_output`` list if present.
    tasks = getattr(result, "tasks_output", None)
    if tasks:
        for t in tasks:
            out = getattr(t, "raw", None) or _safe_text(t)
            if out:
                # Each per-task output is also an LLM call. Use
                # ``record_llm_call`` to keep the counter math consistent.
                collector.record_llm_call(out, ok=True)

    if not text and not tasks:
        # Kickoff produced nothing we could parse — still count it.
        collector.record_llm_call("", ok=True)

def _wrap_tool(original, collector_ref: SignalCollector | None, attr: str):
    import functools
    def sync_call(self, *args, **kwargs):
        from .base import resolve_collector
        collector = resolve_collector(self, collector_ref)
        tool_name = getattr(self, "name", "tool")
        
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
            collector.record_error(e, source="crewai")
            collector.record_tool_call(ok=False, action_name=tool_name, tool_args=tool_args)
            raise
    return functools.wraps(original)(sync_call)
