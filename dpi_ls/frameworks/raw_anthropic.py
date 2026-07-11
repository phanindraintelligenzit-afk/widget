"""Raw Anthropic client patcher.

Same shape as the OpenAI patcher: walk the client, find every
``.create`` (Anthropic exposes ``client.messages.create``), wrap it,
and record each call into the collector.

Anthropic token usage shape is ``usage.input_tokens`` /
``usage.output_tokens`` — the base helper already handles that.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from ..collector import SignalCollector
from .base import BasePatcher, _safe_iter_tokens, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.raw_anthropic")


class RawAnthropicPatcher(BasePatcher):
    name = "anthropic"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        from .raw_openai import _walk_create_methods, _set_attr_path

        patched: list[str] = []
        for path, method in _walk_create_methods(agent):
            if already_patched(method):
                continue
            wrapped = _wrap_create(method, collector)
            try:
                _set_attr_path(agent, path, wrapped)
                mark_patched(wrapped)
                patched.append(".".join(path))
            except (AttributeError, TypeError):
                _log.debug("Could not patch %s (read-only).", ".".join(path))
        if patched:
            _log.debug("Patched Anthropic client: %s", patched)
        return patched


def _wrap_create(original, collector: SignalCollector):
    import inspect
    is_coro = inspect.iscoroutinefunction(original)

    if is_coro:
        async def async_create(*args, **kwargs):
            collector.attempts += 1
            try:
                response = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="anthropic")
                raise
            _record_response(collector, response)
            return response
        return functools.wraps(original)(async_create)

    def sync_create(*args, **kwargs):
        collector.attempts += 1
        try:
            response = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="anthropic")
            raise
        _record_response(collector, response)
        return response
    return functools.wraps(original)(sync_create)


def _record_response(collector: SignalCollector, response: Any) -> None:
    text = _safe_text(response)
    in_t, out_t = _safe_iter_tokens(response)
    if text:
        collector.record_llm_call(text, tokens_in=in_t, tokens_out=out_t, ok=True)
    else:
        collector.successful += 1
