"""OpenAI Agents SDK patcher.

The SDK exposes ``Runner.run`` / ``Runner.run_sync`` / ``Runner.run_streamed``
as the three entry points. Each accepts a ``hooks=`` keyword that
receives lifecycle callbacks (``on_agent_start``, ``on_llm_start``,
``on_llm_end``, ``on_tool_start``, ``on_tool_end``, ``on_agent_end``).
We wrap the entry points so our hook object is injected automatically
— the user never has to pass it themselves.

We also wrap the underlying ``Runner.run`` (an ``AgentRunner`` class
method) because the SDK stores the *current* set of hooks in
``RunConfig`` and some user code constructs its own. Wrapping
``Runner.run`` makes the instrumentation sticky without forcing the
user to refactor.
"""
from __future__ import annotations

import logging
from typing import Any

from ..collector import SignalCollector
from .base import BasePatcher, _extract_input_text, _safe_iter_tokens, _safe_text, already_patched, mark_patched

_log = logging.getLogger("dpi_ls.frameworks.openai_agents")


def _make_hooks(collector: SignalCollector):
    """Build a RunHooks subclass bound to this collector.

    Imported lazily — ``agents`` is an optional dep on the user's
    machine, and we don't want to fail at import time if they only
    use LangGraph.
    """
    from agents import RunContextWrapper, RunHooks  # type: ignore

    class _Hooks(RunHooks):  # type: ignore[misc]
        async def on_agent_start(self, context, agent):  # type: ignore[override]
            # Just capture the agent name — don't increment attempts here.
            # attempts is driven exclusively by record_llm_call / record_tool_call
            # to avoid double-counting (on_llm_start + on_llm_end both fire).
            if not collector.agent_name and getattr(agent, "name", None):
                collector.agent_name = agent.name

        async def on_llm_start(self, context, agent, system_prompt, input_items):  # type: ignore[override]
            # No-op: on_llm_end drives the attempt counter via record_llm_call.
            pass

        async def on_llm_end(self, context, agent, response):  # type: ignore[override]
            text = _safe_text(response)
            in_t, out_t = _safe_iter_tokens(response)
            # Estimate cost from tokens if no explicit cost is available.
            # Uses a conservative $0.001 per 1k tokens blended rate so C
            # is non-zero when Bedrock/LiteLLM doesn't return dollar amounts.
            total_tokens = in_t + out_t
            est_cost = total_tokens * 0.000001  # $0.001 per 1k tokens
            collector.record_llm_call(
                text, tokens_in=in_t, tokens_out=out_t, cost=est_cost, ok=True,
            )

        async def on_tool_start(self, context, agent, tool):  # type: ignore[override]
            # No-op: on_tool_end drives the counter.
            pass

        async def on_tool_end(self, context, agent, tool, result):  # type: ignore[override]
            # Record as a successful tool call. Capture the tool result text
            # for V/G scoring (structured output check + policy scan) but tag
            # it as 'tool' so it is NOT sent to the Q LLM evaluator — the LLM
            # cannot verify factual accuracy of raw API data.
            text = _safe_text(result)
            tool_name = getattr(tool, "name", "tool")
            collector.record_tool_call(ok=True, action_name=tool_name)
            if text:
                collector._capture_output(text, kind="tool")

        async def on_agent_end(self, context, agent, output):  # type: ignore[override]
            text = _safe_text(output)
            if text:
                # Final agent output captured for Q evaluation.
                collector._capture_output(text)

    hooks = _Hooks()
    # Attach the collector so _wrap_runner_method can call record_agent_run
    # without needing a separate closure variable.
    hooks._dpi_ls_collector = collector  # type: ignore[attr-defined]
    return hooks


class OpenAIAgentsPatcher(BasePatcher):
    name = "openai_agents"
    one_run = False  # user may call Runner.run many times in one script

    def install(self, agent: Any, collector: SignalCollector) -> list[str]:
        try:
            from agents import Runner  # type: ignore
        except ImportError:
            _log.debug("OpenAI Agents SDK not installed; skipping patch.")
            return []
        hooks = _make_hooks(collector)
        # Mark the agent too — some user code creates its own hooks and
        # we want to *cooperate*, not collide. We don't override the
        # user's hooks; we just add ours alongside via a wrapper that
        # passes both lists to Runner.run.
        patched: list[str] = []
        for attr in ("run", "run_sync", "run_streamed"):
            original = getattr(Runner, attr, None)
            if original is None or already_patched(original):
                continue
            wrapped = _wrap_runner_method(original, hooks)
            setattr(Runner, attr, wrapped)
            mark_patched(wrapped)
            patched.append(f"agents.Runner.{attr}")
        if patched:
            _log.debug("Patched OpenAI Agents Runner: %s", patched)
        return patched


def _wrap_runner_method(original, hooks):
    """Return a wrapper that injects our hooks, records the agent run
    result for the P dimension, and preserves the user's existing
    ``hooks=`` if they passed one."""
    import functools
    import inspect

    # hooks carries a reference to the collector via its closure.
    # We reach it through the hooks object so the wrapper always uses
    # the *current* collector, not a stale one from a previous monitor() call.
    _collector = getattr(hooks, "_dpi_ls_collector", None)

    if inspect.iscoroutinefunction(original):
        async def async_wrapper(*args, **kwargs):
            # Runner.run(agent, task, ...) — task is the second positional arg.
            task_text = args[1] if len(args) > 1 else _extract_input_text(args, kwargs)
            if _collector is not None and isinstance(task_text, str) and task_text:
                _collector.record_source(task_text, kind="input")
            existing = kwargs.get("hooks")
            if existing is None:
                kwargs["hooks"] = hooks
            else:
                kwargs["hooks"] = _compose_hooks(existing, hooks)
            try:
                result = await original(*args, **kwargs)
                if _collector is not None:
                    _collector.record_agent_run(ok=True)
                return result
            except Exception:
                if _collector is not None:
                    _collector.record_agent_run(ok=False)
                raise
        return functools.wraps(original)(async_wrapper)

    def sync_wrapper(*args, **kwargs):
        task_text = args[1] if len(args) > 1 else _extract_input_text(args, kwargs)
        if _collector is not None and isinstance(task_text, str) and task_text:
            _collector.record_source(task_text, kind="input")
        existing = kwargs.get("hooks")
        if existing is None:
            kwargs["hooks"] = hooks
        else:
            kwargs["hooks"] = _compose_hooks(existing, hooks)
        try:
            result = original(*args, **kwargs)
            if _collector is not None:
                _collector.record_agent_run(ok=True)
            return result
        except Exception:
            if _collector is not None:
                _collector.record_agent_run(ok=False)
            raise
    return functools.wraps(original)(sync_wrapper)


def _compose_hooks(user_hooks, our_hooks):
    """Build a RunHooks subclass that calls BOTH sets of hooks.

    The OpenAI Agents SDK treats the single ``hooks=`` argument as one
    object with on_* methods. To support the user passing their own
    hooks alongside ours, we build a forwarder that calls into both.
    """
    from agents import RunHooks  # type: ignore

    class _Both(RunHooks):  # type: ignore[misc]
        async def on_agent_start(self, context, agent):
            await user_hooks.on_agent_start(context, agent)
            await our_hooks.on_agent_start(context, agent)

        async def on_agent_end(self, context, agent, output):
            await user_hooks.on_agent_end(context, agent, output)
            await our_hooks.on_agent_end(context, agent, output)

        async def on_llm_start(self, context, agent, system_prompt, input_items):
            await user_hooks.on_llm_start(context, agent, system_prompt, input_items)
            await our_hooks.on_llm_start(context, agent, system_prompt, input_items)

        async def on_llm_end(self, context, agent, response):
            await user_hooks.on_llm_end(context, agent, response)
            await our_hooks.on_llm_end(context, agent, response)

        async def on_tool_start(self, context, agent, tool):
            await user_hooks.on_tool_start(context, agent, tool)
            await our_hooks.on_tool_start(context, agent, tool)

        async def on_tool_end(self, context, agent, tool, result):
            await user_hooks.on_tool_end(context, agent, tool, result)
            await our_hooks.on_tool_end(context, agent, tool, result)

        async def on_handoff(self, context, from_agent, to_agent):
            # Some SDK versions have this; not all. Best-effort.
            if hasattr(user_hooks, "on_handoff"):
                await user_hooks.on_handoff(context, from_agent, to_agent)
            if hasattr(our_hooks, "on_handoff"):
                await our_hooks.on_handoff(context, from_agent, to_agent)

    return _Both()
