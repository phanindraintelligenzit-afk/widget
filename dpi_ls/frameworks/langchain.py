"""LangChain patcher.

A LangChain "agent" is a ``Runnable`` (typically a ``RunnableSequence``
or a compiled agent executor). The runnable API is uniform: ``invoke``
(sync), ``ainvoke`` (async), ``stream`` / ``astream`` (streaming).

We wrap the four methods on the runnable. Token usage is taken from
the runnable's response metadata if available (LangChain puts
``usage_metadata`` on AIMessages) — otherwise we record the text only
and let the C dimension stay cold.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from ..collector import SignalCollector
from .base import BasePatcher, _extract_input_text, _safe_iter_tokens, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.langchain")


class LangChainPatcher(BasePatcher):
    name = "langchain"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        patched: list[str] = []

        def _patch_obj(target, label):
            for attr in ("invoke", "ainvoke", "stream", "astream"):
                original = getattr(target, attr, None)
                if original is None or already_patched(original):
                    continue
                wrapped = _wrap_runnable(original, collector, attr)
                try:
                    setattr(target, attr, wrapped)
                    mark_patched(wrapped)
                    patched.append(f"{label}.{attr}")
                except (AttributeError, TypeError, ValueError):
                    try:
                        object.__setattr__(target, attr, wrapped)
                        mark_patched(wrapped)
                        patched.append(f"{label}.{attr}")
                    except Exception as inner:
                        _log.debug("Could not patch %s.%s: %s", label, attr, inner)
        # Optionally patch the specific agent passed in, if it's a Runnable.
        _patch_obj(agent, "runnable")

        # Globally patch BaseTool so any dynamically instantiated tools are captured automatically.
        try:
            from langchain_core.tools import BaseTool
            _patch_obj(BaseTool, "tool_class")
        except ImportError:
            pass

        if patched:
            _log.debug("Patched LangChain instances/classes: %s", patched)
        return patched


def _wrap_runnable(original, collector: SignalCollector, attr: str):
    import inspect

    is_async = attr.startswith("a")
    is_stream = attr.endswith("stream")
    def _get_runnable_info(args):
        # Try to extract from the instance (args[0]) if this is an unbound method patch,
        # otherwise fall back to the original object.
        runnable_obj = original
        if args and hasattr(args[0], "__class__"):
            # Check if args[0] is likely the instance we're bound to
            if hasattr(args[0], "invoke") or hasattr(args[0], "ainvoke"):
                runnable_obj = args[0]
        else:
            runnable_obj = getattr(original, "__self__", original)

        r_name = getattr(runnable_obj, "name", None)
        if not r_name:
            r_name = getattr(runnable_obj, "__name__", None)
        if not r_name and hasattr(runnable_obj, "__class__"):
            r_name = runnable_obj.__class__.__name__

        is_t = hasattr(runnable_obj, "args_schema") or "Tool" in getattr(getattr(runnable_obj, "__class__", None), "__name__", "")
        return r_name, is_t

    if is_async and is_stream:
        async def async_stream(*args, **kwargs):
            runnable_name, is_tool = _get_runnable_info(args)
            try:
                async for chunk in original(*args, **kwargs):
                    yield chunk
            except Exception as e:
                collector.record_error(e, source="langchain")
                if is_tool:
                    collector.record_tool_call(ok=False, action_name=runnable_name)
                else:
                    collector.record_llm_call("", ok=False, system=runnable_name, action_name=runnable_name)
                raise
            if is_tool:
                collector.record_tool_call(ok=True, action_name=runnable_name)
            else:
                collector.record_llm_call("", ok=True, system=runnable_name, action_name=runnable_name)
        return functools.wraps(original)(async_stream)

    if is_async:
        async def async_invoke(*args, **kwargs):
            runnable_name, is_tool = _get_runnable_info(args)
            input_text = _extract_input_text(args, kwargs)
            if input_text:
                collector.record_source(input_text, kind="input")
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="langchain")
                if is_tool:
                    collector.record_tool_call(ok=False, action_name=runnable_name)
                else:
                    collector.record_llm_call("", ok=False, system=input_text or runnable_name, action_name=runnable_name)
                raise
            _capture_runnable_result(collector, result, is_tool, system=input_text or runnable_name, action_name=runnable_name)
            return result
        return functools.wraps(original)(async_invoke)

    if is_stream:
        def sync_stream(*args, **kwargs):
            runnable_name, is_tool = _get_runnable_info(args)
            try:
                yield from original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="langchain")
                if is_tool:
                    collector.record_tool_call(ok=False, action_name=runnable_name)
                else:
                    collector.record_llm_call("", ok=False, system=runnable_name, action_name=runnable_name)
                raise
            if is_tool:
                collector.record_tool_call(ok=True, action_name=runnable_name)
            else:
                collector.record_llm_call("", ok=True, system=runnable_name, action_name=runnable_name)
        return functools.wraps(original)(sync_stream)

    def sync_invoke(*args, **kwargs):
        runnable_name, is_tool = _get_runnable_info(args)
        input_text = _extract_input_text(args, kwargs)
        if input_text:
            collector.record_source(input_text, kind="input")
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="langchain")
            if is_tool:
                collector.record_tool_call(ok=False, action_name=runnable_name)
            else:
                collector.record_llm_call("", ok=False, system=input_text or runnable_name, action_name=runnable_name)
            raise
        _capture_runnable_result(collector, result, is_tool, system=input_text or runnable_name, action_name=runnable_name)
        return result
    return functools.wraps(original)(sync_invoke)


def _capture_runnable_result(collector: SignalCollector, result: Any, is_tool: bool, system: str | None = None, action_name: str | None = None) -> None:
    text = _safe_text(result)
    in_t, out_t = _safe_iter_tokens(result)
    if is_tool:
        ok = True
        if isinstance(result, dict) and "return_code" in result:
            ok = result["return_code"] == 0
        collector.record_tool_call(ok=ok, action_name=action_name)
    else:
        if text:
            collector.record_llm_call(text, tokens_in=in_t, tokens_out=out_t, ok=True, system=system, action_name=action_name)
        else:
            collector.record_llm_call("", ok=True, system=system, action_name=action_name)
