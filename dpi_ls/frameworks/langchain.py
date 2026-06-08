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
            # Pydantic v2 models (e.g. ``RunnableSequence``) raise ``ValueError``
            # when you try to setattr an unknown field. Older code paths raise
            # ``AttributeError`` / ``TypeError`` — catch all three so a frozen
            # model doesn't kill the whole patcher install.
            except (AttributeError, TypeError, ValueError):
                # Bypass the Pydantic validator by writing the attribute onto
                # the instance __dict__ directly. Pydantic v2 only intercepts
                # ``__setattr__``; ``object.__setattr__`` is untouched and
                # still works on frozen / extra-forbidden models.
                try:
                    object.__setattr__(agent, attr, wrapped)
                    mark_patched(wrapped)
                    patched.append(f"runnable.{attr}")
                    _log.debug(
                        "Patched runnable.%s via object.__setattr__ (Pydantic v2 model).",
                        attr,
                    )
                except Exception as inner:  # pragma: no cover - truly frozen
                    _log.debug(
                        "Could not patch runnable.%s (read-only, even via __dict__): %s",
                        attr, inner,
                    )
        if patched:
            _log.debug("Patched LangChain runnable: %s", patched)
        return patched


def _wrap_runnable(original, collector: SignalCollector, attr: str):
    import inspect

    is_async = attr.startswith("a")
    is_stream = attr.endswith("stream")

    if is_async and is_stream:
        async def async_stream(*args, **kwargs):
            # No pre-increment: ``record_llm_call`` (called via
            # ``_capture_runnable_result``) owns the attempts counter.
            # ``record_error`` handles the failure path.
            try:
                async for chunk in original(*args, **kwargs):
                    yield chunk
            except Exception as e:
                collector.record_error(e, source="langchain")
                raise
            # The stream yielded without raising; record one successful
            # empty call so E reflects the work that happened.
            collector.record_llm_call("", ok=True)
        return functools.wraps(original)(async_stream)

    if is_async:
        async def async_invoke(*args, **kwargs):
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
            try:
                yield from original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="langchain")
                raise
            collector.record_llm_call("", ok=True)
        return functools.wraps(original)(sync_stream)

    def sync_invoke(*args, **kwargs):
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
        # No text but the call still completed — count it as a successful
        # execution so E is non-zero for chains that don't surface text.
        collector.record_llm_call("", ok=True)
