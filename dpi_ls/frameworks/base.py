"""Base class for framework-specific patchers.

A patcher wraps (or monkey-patches) one framework's "run an agent"
entry point so that, as the user's code calls it, the
``SignalCollector`` records attempts, outputs, errors, and token usage.

The contract is intentionally minimal:

* ``name`` — short identifier for logs / the observation's source field.
* ``install(agent, collector)`` — patch whatever needs patching so
  that the NEXT call to the framework's run entry point is observable.
  Returns a list of attribute paths that were replaced (for tests).

Patches must be **idempotent**: calling ``install`` twice from the same
``monitor()`` must not stack hooks or replace already-replaced methods
a second time. We use ``_patched`` as a sentinel on the wrapped
function.

Patches must be **transparent**: the wrapper must return exactly the
same type as the original. If the user awaits ``Runner.run`` we must
still return a coroutine; if they iterate a streamed response we must
still yield chunks. Subclasses document the specific return-type
contract they preserve.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from ..collector import SignalCollector


# Sentinel attribute attached to wrapped callables so we can detect
# "already patched" without re-walking the MRO.
_PATCHED_FLAG = "_dpi_ls_patched"


def already_patched(fn: Any) -> bool:
    return bool(getattr(fn, _PATCHED_FLAG, False))


def mark_patched(fn: Any) -> None:
    try:
        setattr(fn, _PATCHED_FLAG, True)
    except (AttributeError, TypeError):  # pragma: no cover - some C funcs
        pass


class BasePatcher:
    """One per supported framework. Stateless aside from install bookkeeping."""

    #: Short name — recorded in AgentObservation.source.
    name: str = "unknown"

    #: True for frameworks that ALWAYS count one logical "run" per install.
    #: If False, signals accumulate across as many calls as the user makes.
    one_run: bool = False

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        """Wire the framework to the collector. Return list of patched paths."""
        raise NotImplementedError

    def uninstall(self) -> None:
        """Best-effort rollback. Tests use this; production doesn't need it."""
        # Default: no-op. Subclasses override if they keep a list of swaps.


# ---------------------------------------------------------------------------
# Collector-swap-on-reinstall — shared by all patchers so that
# ``detect_and_install(obj, c1)`` followed by ``detect_and_install(obj, c2)``
# re-targets the existing wrappers at c2 (matching the UnknownPatcher's
# behaviour and the ``test_install_is_idempotent`` contract).
# ---------------------------------------------------------------------------

# Attribute name attached to the agent instance. The value is a
# ``list[SignalCollector]`` with one element — the *current* collector.
# Wrappers read ``_collector_ref[0]`` on every call so a swap on
# re-install takes effect immediately.
_COLLECTOR_REF_ATTR = "_dpi_ls_collector_ref"


def attach_collector_ref(agent: Any, collector: SignalCollector) -> list:
    """Attach (or update) a mutable collector reference on ``agent``.

    Returns the list. On a second call we mutate the existing list in
    place so the already-installed wrappers pick up the new collector
    on their next invocation.
    """
    existing = getattr(agent, _COLLECTOR_REF_ATTR, None)
    if existing is not None:
        existing[0] = collector
        return existing
    ref: list = [collector]
    try:
        object.__setattr__(agent, _COLLECTOR_REF_ATTR, ref)
    except (AttributeError, TypeError):
        # Some objects don't allow arbitrary attribute setting (e.g.
        # certain C-extension types). Fall back to setting on the class
        # — less ideal but still works.
        try:
            setattr(type(agent), _COLLECTOR_REF_ATTR, ref)
        except (AttributeError, TypeError):
            pass
    return ref


def resolve_collector(agent: Any, fallback) -> SignalCollector:
    """Return the active collector for ``agent``.

    Priority:
      1. ``_state.get_collector()`` — wins when ``monitor()`` set the
         state (handles multi-monitor scenarios where the second call
         takes over).
      2. The mutable reference attached to the agent — survives
         re-installs in tests.
      3. The closure-captured fallback — used only when neither of
         the above is set (e.g. direct patcher use in tests).
    """
    from .. import _state  # local import — avoids a top-level cycle
    cur = _state.get_collector()
    if cur is not None:
        return cur
    ref = getattr(agent, _COLLECTOR_REF_ATTR, None)
    if ref is not None and ref[0] is not None:
        return ref[0]
    return fallback


def _safe_iter_tokens(response: Any) -> tuple[int, int]:
    """Pull (input_tokens, output_tokens) from a response object's
    ``usage`` / ``usage_metadata`` field, in whatever shape the framework uses.

    Handles OpenAI, Anthropic, LiteLLM, Bedrock, and the LangChain
    normalized ``usage_metadata`` shape. Returns (0, 0) if nothing
    readable is found — worst case is a cold C dimension, never a crash.
    """
    # Check both ``usage`` (OpenAI / Anthropic / raw clients) and
    # ``usage_metadata`` (LangChain's normalized attribute) so we work
    # for either shape.
    usage = getattr(response, "usage", None)
    if usage is None:
        usage = getattr(response, "usage_metadata", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage") or response.get("usage_metadata")
    if usage is None:
        return 0, 0

    # OpenAI / LiteLLM shape: prompt_tokens + completion_tokens.
    in_t = (getattr(usage, "prompt_tokens", None)
            or getattr(usage, "input_tokens", None))
    if in_t is None and isinstance(usage, dict):
        in_t = usage.get("prompt_tokens") or usage.get("input_tokens")

    out_t = (getattr(usage, "completion_tokens", None)
             or getattr(usage, "output_tokens", None))
    if out_t is None and isinstance(usage, dict):
        out_t = usage.get("completion_tokens") or usage.get("output_tokens")

    # LiteLLM sometimes exposes a total_tokens only; split 2/3 : 1/3.
    if in_t is None and out_t is None:
        total = getattr(usage, "total_tokens", None)
        if total is None and isinstance(usage, dict):
            total = usage.get("total_tokens")
        if total:
            in_t = int(total * 0.67)
            out_t = int(total * 0.33)

    try:
        return int(in_t or 0), int(out_t or 0)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0, 0


def _safe_text(response: Any) -> str:
    """Best-effort text extraction from a framework response.

    Returns "" if nothing readable is found. Strings are returned as-is
    (the common case when the framework has already unwrapped the
    message for us).

    For dicts that don't carry a recognized 'content'/'text'/'output' key
    (e.g. raw tool results like a Cost Explorer response), we JSON-encode
    the whole dict so the collector can run policy + validation checks on
    the actual payload.
    """
    # None or primitive non-string types — no useful text.
    if response is None or isinstance(response, (int, float, bool)):
        return ""
    # Plain string — most common case after the wrapper unwraps.
    if isinstance(response, str):
        return response
    # LangChain AIMessage and OpenAI ChatCompletion both expose ``content``.
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        # Try well-known keys first.
        content = response.get("content") or response.get("text") or response.get("output")
        if content is None:
            # Arbitrary dict (e.g. tool result) — JSON-encode so the
            # collector can see it as a structured output for V scoring.
            try:
                return json.dumps(response, default=str)
            except Exception:  # pragma: no cover
                return str(response)
    if content is None:
        # Non-dict object with no content attr and no known key —
        # only stringify if it's not a bare object with no useful repr.
        return ""
    if isinstance(content, str):
        return content
    # OpenAI returns a list of content parts for multi-modal responses.
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if "text" in part:
                    parts.append(str(part["text"]))
                elif "content" in part:
                    parts.append(str(part["content"]))
            else:
                parts.append(str(part))
        return "\n".join(parts)
    return str(content)
