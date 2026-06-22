"""AutoGen patcher.

AutoGen is the messiest of the supported frameworks — there are
several "agent" classes (``AssistantAgent``, ``UserProxyAgent``,
``ConversableAgent``, ``GroupChatManager``) and several ways to drive
them (``initiate_chat``, ``generate_reply``, ``a_generate_reply``).

We take a defensive approach: wrap the *agent object's* ``initiate_chat``
method (the most common entry point). If that's not present, we wrap
``generate_reply`` as a fallback.

Because AutoGen agents can call each other in chains, we treat each
``initiate_chat`` invocation as one "run" that the collector observes.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from ..collector import SignalCollector
from .base import BasePatcher, _extract_input_text, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.autogen")


class AutoGenPatcher(BasePatcher):
    name = "autogen"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        patched: list[str] = []
        # Initiate_chat may be sync or async depending on the AutoGen
        # version. Wrap both if both exist.
        for attr in ("initiate_chat", "a_initiate_chat", "generate_reply", "a_generate_reply"):
            original = getattr(agent, attr, None)
            if original is None or already_patched(original):
                continue
            wrapped = _wrap_method(original, collector, attr)
            try:
                setattr(agent, attr, wrapped)
                mark_patched(wrapped)
                patched.append(f"agent.{attr}")
            except (AttributeError, TypeError):
                _log.debug("Could not patch agent.%s (read-only).", attr)
                
        # Patch tool execution
        for attr in ("execute_function", "a_execute_function"):
            original = getattr(agent, attr, None)
            if original is None or already_patched(original):
                continue
            wrapped = _wrap_autogen_tool(original, collector, attr)
            try:
                setattr(agent, attr, wrapped)
                mark_patched(wrapped)
                patched.append(f"agent.{attr}")
            except (AttributeError, TypeError):
                pass
                
        if patched:
            _log.debug("Patched AutoGen agent: %s", patched)
        return patched


def _wrap_method(original, collector: SignalCollector, attr: str):
    import inspect
    is_async = attr.startswith("a_")

    if is_async:
        async def async_wrapper(*args, **kwargs):
            input_text = _extract_input_text(args, kwargs)
            if input_text:
                collector.record_source(input_text, kind="input")
            collector.attempts += 1
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="autogen")
                raise
            _capture_text(collector, result)
            return result
        return functools.wraps(original)(async_wrapper)

    def sync_wrapper(*args, **kwargs):
        input_text = _extract_input_text(args, kwargs)
        if input_text:
            collector.record_source(input_text, kind="input")
        collector.attempts += 1
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="autogen")
            raise
        _capture_text(collector, result)
        return result
    return functools.wraps(original)(sync_wrapper)


def _capture_text(collector: SignalCollector, result: Any) -> None:
    if result is None:
        collector.successful += 1
        return
    text = _safe_text(result)
    if text:
        collector.record_llm_call(text, ok=True)
    else:
        collector.successful += 1


def _wrap_autogen_tool(original, collector: SignalCollector, attr: str):
    import functools
    is_async = attr.startswith("a_")
    
    if is_async:
        async def async_wrapper(self, func_call, *args, **kwargs):
            tool_name = func_call.get("name", "tool") if isinstance(func_call, dict) else "tool"
            tool_args = func_call.get("arguments", {}) if isinstance(func_call, dict) else {}
            if isinstance(tool_args, str):
                try:
                    import json
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {"input": tool_args}
            try:
                result = await original(self, func_call, *args, **kwargs)
                collector.record_tool_call(ok=True, action_name=tool_name, tool_args=tool_args)
                return result
            except Exception as e:
                collector.record_error(e, source="autogen")
                collector.record_tool_call(ok=False, action_name=tool_name, tool_args=tool_args)
                raise
        return functools.wraps(original)(async_wrapper)
    else:
        def sync_wrapper(self, func_call, *args, **kwargs):
            tool_name = func_call.get("name", "tool") if isinstance(func_call, dict) else "tool"
            tool_args = func_call.get("arguments", {}) if isinstance(func_call, dict) else {}
            if isinstance(tool_args, str):
                try:
                    import json
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {"input": tool_args}
            try:
                result = original(self, func_call, *args, **kwargs)
                collector.record_tool_call(ok=True, action_name=tool_name, tool_args=tool_args)
                return result
            except Exception as e:
                collector.record_error(e, source="autogen")
                collector.record_tool_call(ok=False, action_name=tool_name, tool_args=tool_args)
                raise
        return functools.wraps(original)(sync_wrapper)
