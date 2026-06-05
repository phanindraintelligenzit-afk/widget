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
from .base import BasePatcher, _safe_iter_tokens, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.langchain")


class LangChainPatcher(BasePatcher):
    name = "langchain"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        patched: list[str] = []
        for attr in ("invoke", "ainvoke", "stream", "astream"):
            original = getattr(agent, attr, None)
            if original is None or already_patched(original):
                continue
            wrapped = _wrap_runnable(original, collector, attr)
            try:
                setattr(agent, attr, wrapped)
                mark_patched(wrapped)
                patched.append(f"runnable.{attr}")
            except (AttributeError, TypeError):
                _log.debug("Could not patch runnable.%s (read-only).", attr)
        if patched:
            _log.debug("Patched LangChain runnable: %s", patched)
        return patched


def _wrap_runnable(original, collector: SignalCollector, attr: str):
    import inspect

    is_async = attr.startswith("a")
    is_stream = attr.endswith("stream")

    if is_async and is_stream:
        async def async_stream(*args, **kwargs):
            collector.attempts += 1
            try:
                async for chunk in original(*args, **kwargs):
                    yield chunk
            except Exception as e:
                collector.record_error(e, source="langchain")
                raise
            collector.successful += 1
        return functools.wraps(original)(async_stream)

    if is_async:
        async def async_invoke(*args, **kwargs):
            collector.attempts += 1
            try:
                result = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="langchain")
                raise
            _capture_runnable_result(collector, result)
            return result
        return functools.wraps(original)(async_invoke)

    if is_stream:
        def sync_stream(*args, **kwargs):
            collector.attempts += 1
            try:
                yield from original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="langchain")
                raise
            collector.successful += 1
        return functools.wraps(original)(sync_stream)

    def sync_invoke(*args, **kwargs):
        collector.attempts += 1
        try:
            result = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="langchain")
            raise
        _capture_runnable_result(collector, result)
        return result
    return functools.wraps(original)(sync_invoke)


def _capture_runnable_result(collector: SignalCollector, result: Any) -> None:
    text = _safe_text(result)
    in_t, out_t = _safe_iter_tokens(result)
    if text:
        collector.record_llm_call(text, tokens_in=in_t, tokens_out=out_t, ok=True)
    else:
        collector.successful += 1
