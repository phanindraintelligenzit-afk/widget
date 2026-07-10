"""Raw OpenAI client patcher.

When the user passes an ``openai.OpenAI`` (sync) or
``openai.AsyncOpenAI`` (async) client as their "agent", we patch
``client.chat.completions.create`` and (when present)
``client.responses.create``. We also walk the client to find any
nested resources that expose ``.create`` and patch them too.

Each ``create`` call is one observation. Token counts come from the
response's ``usage`` field, in the standard OpenAI shape.
"""
from __future__ import annotations

import functools
import logging
from typing import Any

from ..collector import SignalCollector
from .base import BasePatcher, _safe_iter_tokens, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.raw_openai")


class RawOpenAIPatcher(BasePatcher):
    name = "openai"
    one_run = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        patched: list[str] = []
        # The OpenAI v2 client surfaces the chat and responses resources
        # as attributes. Walk the public API and patch any ``.create``
        # we can find. ``_walk_create_methods`` is a generator.
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
            _log.debug("Patched OpenAI client: %s", patched)
        return patched


def _walk_create_methods(root: Any):
    """Yield (path, method) for every callable ``.create`` found under root.

    Path is a list of attribute names from ``root`` to the method. Used
    both for patching and (by tests) for assertions.
    """
    seen: set[int] = set()
    stack: list[tuple[list[str], Any]] = [([""], root)]
    while stack:
        path, obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        # If this is a callable ``.create``, yield it.
        if callable(obj) and path and path[-1] == "create":
            yield path, obj
            continue
        # Walk attributes one level deep. Limit depth to avoid
        # wandering into HTTP internals.
        if len(path) > 4:
            continue
        for name in dir(obj):
            if name.startswith("_"):
                continue
            try:
                child = getattr(obj, name)
            except Exception:  # noqa: BLE001
                continue
            if not (callable(child) or hasattr(child, "__dict__")):
                continue
            stack.append((path + [name], child))


def _set_attr_path(root: Any, path: list[str], value: Any) -> None:
    """Assign ``value`` at ``root.<a>.<b>.<c>`` following the path list."""
    target = root
    for name in path[:-1]:
        target = getattr(target, name)
    setattr(target, path[-1], value)


def _wrap_create(original, collector: SignalCollector):
    import inspect
    is_coro = inspect.iscoroutinefunction(original)

    if is_coro:
        async def async_create(*args, **kwargs):
            collector.attempts += 1
            try:
                response = await original(*args, **kwargs)
            except Exception as e:
                collector.record_error(e, source="openai")
                raise
            _record_response(collector, response)
            return response
        return functools.wraps(original)(async_create)

    def sync_create(*args, **kwargs):
        collector.attempts += 1
        try:
            response = original(*args, **kwargs)
        except Exception as e:
            collector.record_error(e, source="openai")
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
        # No text content (e.g. a tool call) — still a successful call.
        collector.successful += 1
