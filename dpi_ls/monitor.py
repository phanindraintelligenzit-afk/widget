"""The public ``dpi_ls.monitor()`` entrypoint.

The shape is exactly the two-line integration the spec asks for::

    import dpi_ls
    dpi_ls.monitor(agent, agent_id="my-agent")

What ``monitor()`` does, in order:

1. Starts the FastAPI dashboard in a background thread (idempotent —
   second call is a no-op).
2. Builds a :class:`SignalCollector` for this run.
3. Detects the framework from the ``agent`` object's class and installs
   the matching patcher. Patches accumulate signals into the collector
   as the user runs the agent.
4. Registers an ``atexit`` finalizer that, when the script exits,
   runs the LangGraph Q evaluator, builds the canonical
   ``AgentObservation``, and POSTs it to ``/ingest``.
5. If ``block=True`` (the default) and we're attached to a TTY, the
   finalizer also calls ``input()`` so the user can browse the
   dashboard before the script exits. The dashboard is alive in a
   daemon thread regardless.

Two flags give the user escape hatches:

* ``block=False``  — don't pause on exit (CI / non-interactive).
* ``post=False``  — don't POST the final observation (debugging / tests).
* ``open_browser=False`` — don't pop the browser tab.
"""
from __future__ import annotations

import atexit
import logging
import os
import sys
import threading
from typing import Any, Optional

from . import _state
from .collector import SignalCollector
from .evaluator import evaluate_quality
from .frameworks import detect_and_install
from .poster import post_observation, write_local_copy
from .server import start_server

_log = logging.getLogger("dpi_ls.monitor")


def monitor(
    agent: Any,
    agent_id: str,
    agent_name: str | None = None,
    *,
    human_baseline: int | None = None,
    block: bool | None = None,
    post: bool | None = None,
    open_browser: bool | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> SignalCollector:
    """Install instrumentation around ``agent`` and start the dashboard.

    Parameters
    ----------
    agent:
        The framework-specific object the user is about to invoke.
    agent_id:
        Stable identifier for the agent.
    agent_name:
        Human-readable name. Falls back to ``agent_id`` if not supplied.
    human_baseline:
        How many outputs a human would produce in the same period. Used
        to compute **P** (Productivity). For a single-run report agent,
        pass ``1``. For a batch agent processing 100 tickets, pass ``100``.
        Defaults to the existing DB value (100 on first run).
    block:
        If True, pause for Enter on script exit so the dashboard stays
        reachable. Defaults to True when attached to a TTY.
    post:
        If True (the default), POST the final observation to ``/ingest``.
    open_browser:
        If True, pop the dashboard URL in a browser tab.
    host, port:
        Where the dashboard binds. Default ``127.0.0.1:8000``.
    """
    if not agent_id:
        raise ValueError("agent_id is required")

    # Resolve defaults from the environment.
    if block is None:
        block = _default_block()
    if post is None:
        post = _default_post()
    if open_browser is None:
        open_browser = _env_flag("DPI_LS_OPEN_BROWSER", default=False)

    # 1. Boot the dashboard (idempotent).
    info = start_server(
        host=host,
        port=port,
        open_browser=open_browser,
    )
    _state.set_server_info(info)

    # 2. Build the collector and bind it to the agent.
    resolved_name = agent_name or _try_agent_name(agent) or agent_id
    collector = SignalCollector(
        agent_id=agent_id,
        agent_name=resolved_name,
        human_baseline=human_baseline,
    )
    _state.set_collector(collector)

    # 3. Install the framework-specific patcher.
    patched = detect_and_install(agent, collector)
    collector.framework = _infer_framework_from_patches(patched)
    _log.info(
        "dpi_ls: monitoring %s (%s) — patched %s",
        agent_id, collector.framework, ", ".join(patched) or "(nothing matched)",
    )

    # 4. Register the finalizer. atexit handlers run in LIFO order
    #    and on normal interpreter shutdown — including when the
    #    script ends via a SystemExit (e.g. ``sys.exit()`` or just
    #    running off the end of the file).
    if not _state.finalizer_registered():
        atexit.register(_finalize)
        _state.mark_finalizer_registered()

    # 5. Apply the user's overrides for the finalizer behaviour.
    _state.set_block_on_exit(block)
    _state.set_post_on_exit(post)

    return collector


# ---------------------------------------------------------------------------
# Finalizer — runs on script exit
# ---------------------------------------------------------------------------

def _finalize() -> None:
    """Atexit entry point. Runs Q eval, builds observation, posts it.

    Split into a small set of steps so each one can be tested
    individually. All errors are caught and logged; nothing here should
    ever propagate to the interpreter's shutdown path.
    """
    collector = _state.get_collector()
    if collector is None:
        return
    info = _state.get_server_info()

    try:
        collector.mark_end()

        if _state.get_post_on_exit() and info is not None:
            outputs = collector.outputs_for_q()
            # Skip Q evaluation if the caller already ran it explicitly
            # (e.g. inside an async function before asyncio.run returns).
            # Re-running here causes "cannot schedule new futures after
            # interpreter shutdown" because the event loop is tearing down.
            if outputs and collector.quality is None:
                try:
                    q = evaluate_quality(outputs)
                    collector.set_quality(
                        q.accuracy, q.consistency, q.hallucination_rate,
                    )
                    _log.info(
                        "dpi_ls: Q evaluation source=%s accuracy=%.3f "
                        "consistency=%.3f hallucination=%.3f",
                        q.source, q.accuracy, q.consistency, q.hallucination_rate,
                    )
                except Exception as e:  # pragma: no cover - defensive
                    _log.warning("Q evaluation raised: %s", e)

            rating = post_observation(collector, info.base_url)
            if rating is not None:
                _log.info(
                    "dpi_ls: %s scored %.2f (%s)%s",
                    collector.agent_id,
                    rating.get("score", -1),
                    rating.get("band", "?"),
                    " · UNSAFE" if rating.get("unsafe") else "",
                )
            else:
                # Even when the post fails we drop a local copy so
                # the user can inspect / re-ingest manually.
                path = write_local_copy(collector)
                _log.info("dpi_ls: local observation copy at %s", path)
        else:
            # Posting disabled — still drop a local copy.
            path = write_local_copy(collector)
            _log.info("dpi_ls: local observation copy at %s", path)

        # Block at the end so the dashboard stays reachable from a
        # terminal session. Skipped in non-interactive contexts.
        if _state.get_block_on_exit() and sys.stdin is not None and sys.stdin.isatty():
            try:
                print(
                    f"\ndpi_ls: dashboard is live at {info.base_url if info else 'http://127.0.0.1:8000'} — "
                    f"press Enter to exit.",
                    file=sys.stderr,
                )
                input()
            except (EOFError, KeyboardInterrupt):
                pass
    except Exception:  # pragma: no cover - last-resort guard
        _log.exception("dpi_ls: finalizer crashed; suppressing to avoid breaking interpreter shutdown.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _try_agent_name(agent: Any) -> str | None:
    """Best-effort name extraction from a few common framework shapes."""
    # OpenAI Agents: agent.name
    name = getattr(agent, "name", None)
    if isinstance(name, str) and name:
        return name
    # LangChain runnables sometimes carry a get_name().
    get_name = getattr(agent, "get_name", None)
    if callable(get_name):
        try:
            n = get_name()
            if isinstance(n, str) and n:
                return n
        except Exception:  # noqa: BLE001
            pass
    return None


def _infer_framework_from_patches(patched: list[str]) -> str:
    """Map the patched attribute paths back to a human framework name."""
    if not patched:
        return "unknown"
    joined = " ".join(patched).lower()
    if "runner" in joined:
        return "openai_agents"
    if "graph" in joined:
        return "langgraph"
    if "runnable" in joined:
        return "langchain"
    if "crew" in joined:
        return "crewai"
    if "agent.initiate" in joined or "agent.generate" in joined:
        return "autogen"
    if "openai" in joined or "chat" in joined:
        return "openai"
    if "anthropic" in joined or "messages" in joined:
        return "anthropic"
    return "unknown"


def _default_block() -> bool:
    if _env_flag("DPI_LS_NO_BLOCK", default=False):
        return False
    if _env_flag("DPI_LS_BLOCK", default=False):
        return True
    # TTY check — non-interactive shells / CI don't have a stdin to
    # block on. ``sys.stdin`` may be None under ``python -c`` etc.
    return bool(sys.stdin and sys.stdin.isatty())


def _default_post() -> bool:
    if _env_flag("DPI_LS_DASHBOARD", default=True) is False:
        return False
    return True


def _env_flag(name: str, *, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")
