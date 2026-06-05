"""Run all six example agents in one process and populate the dashboard.

Each example gets its own ``dpi_ls.monitor()`` invocation, its own
``agent_id``, and its own finalizer call so its scored
``AgentObservation`` is posted to the running dashboard at
``http://localhost:8000`` independently.

Run::

    uv run examples/run_all.py

Why this exists
---------------

``dpi_ls`` keeps the active ``SignalCollector`` as a process-wide
singleton (``dpi_ls._state._collector``). Calling ``monitor()``
twice overwrites the singleton. To score multiple agents in one
process we therefore:

1. Run the first example, which calls ``monitor()`` and the agent.
2. Call ``dpi_ls.monitor._finalize()`` to force the post to ``/ingest``
   and the Q evaluator.
3. Call ``dpi_ls._state.reset_for_tests()`` so the next
   ``monitor()`` starts with a clean collector.
4. Repeat for each example.

If the orchestrator exits cleanly, the dashboard shows one row per
agent with the framework-specific ``agent_id``.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

# Make sure the example modules can import dpi_ls from the repo root
# when the orchestrator is invoked from anywhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Don't pause for stdin on exit — the orchestrator drives multiple
# examples in sequence and we don't want any of them to block.
os.environ.setdefault("DPI_LS_NO_BLOCK", "1")

import httpx

import dpi_ls
from dpi_ls import _state
from dpi_ls.monitor import _finalize

# Quieter logs — the orchestrator prints its own structured summary.
logging.getLogger("dpi_ls").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Registry — each entry tells the orchestrator which example to drive and
# which callable inside it to invoke. The callables already call
# ``dpi_ls.monitor()`` themselves.
# ---------------------------------------------------------------------------

# (label, agent_id, module, attribute, kind)
#   kind = "async" — await the callable
#   kind = "sync"  — call the callable directly
EXAMPLES: list[tuple[str, str, str, str, str]] = [
    ("Chandra (OpenAI Agents + Bedrock via LiteLLM)", "chandra-finops",      "examples.test_agent",        "run_agent_observation", "async"),
    ("LangGraph research agent",                      "langgraph-research",  "examples.langgraph_research", "main",                  "async"),
    ("LangChain Q&A agent",                           "langchain-qa",        "examples.langchain_qa",       "main",                  "async"),
    ("CrewAI 2-agent research crew",                  "crewai-research",     "examples.crewai_research",    "main",                  "sync"),
    ("AutoGen 0.7+ debate agent",                     "autogen-debate",      "examples.autogen_debate",     "main",                  "async"),
    ("Raw boto3 Bedrock agent",                       "raw-bedrock",         "examples.raw_bedrock",        "main",                  "sync"),
]

DASHBOARD_URL = os.environ.get("DPI_LS_URL", "http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Per-example driver
# ---------------------------------------------------------------------------
def _reset_state() -> None:
    """Clear the singleton collector + server info + finalizer flag.

    This is the test-fixture reset exported by ``dpi_ls._state``. It
    also clears the ``atexit`` finalizer registration so the next
    ``monitor()`` call will register it again — important because the
    finalizer is the one path that actually pushes the observation
    out to ``/ingest``.
    """
    _state.reset_for_tests()


def _run_one(
    label: str,
    fn: Callable[[], Any],
    kind: str,
    agent_id: str,
) -> dict[str, Any] | None:
    """Run one example, force its finalizer, and return the posted rating.

    The ``agent_id`` is passed in (rather than read off the collector) so
    the orchestrator can keep a label ↔ id mapping even after the
    per-example ``_reset_state`` clears the singleton collector.
    """
    print(f"\n=== {label} (agent_id={agent_id}) ===", flush=True)
    try:
        if kind == "async":
            asyncio.run(fn())
        else:
            fn()
    except Exception as e:  # noqa: BLE001
        print(f"  ! run failed: {e}")
        # Force the finalizer anyway so any partial signals are still posted
        # (and the dashboard gets to show an honest "Unsafe" R for this row).
    try:
        _finalize()
    except Exception as e:  # noqa: BLE001
        print(f"  ! finalizer raised: {e}")

    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{DASHBOARD_URL}/agents/{agent_id}/score")
            r.raise_for_status()
            payload = r.json()
            payload["agent_id"] = agent_id  # the API doesn't echo agent_id
            return payload
    except Exception as e:  # noqa: BLE001
        print(f"  ! could not fetch score: {e}")
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"DPI-LS dashboard expected at: {DASHBOARD_URL}")
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{DASHBOARD_URL}/healthz")
            if r.status_code != 200:
                print(f"  ! dashboard not healthy: {r.status_code}")
    except Exception as e:
        print(f"  ! dashboard unreachable: {e}")
        print("    start it first with: uv run uvicorn api.app:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    # Boot the background server once so subsequent monitor() calls reuse it.
    dpi_ls.monitor(  # type: ignore[call-overload]
        agent=_NoopAgent(),
        agent_id="orchestrator-bootstrap",
        agent_name="Orchestrator Bootstrap",
        block=False,
        post=False,  # the bootstrap shouldn't post anything
    )
    _state.reset_for_tests()

    summary_rows: list[dict[str, Any]] = []

    for label, agent_id, module_name, attr, kind in EXAMPLES:
        module = importlib.import_module(module_name)
        fn = getattr(module, attr)
        rating = _run_one(label, fn, kind, agent_id)
        _reset_state()
        if rating is not None:
            summary_rows.append(
                {
                    "label": label,
                    "agent_id": agent_id,
                    "score": rating.get("score"),
                    "band": rating.get("band"),
                    "unsafe": rating.get("unsafe"),
                    "coverage": rating.get("coverage"),
                }
            )

    print("\n=== Dashboard summary ===")
    print(f"{'agent_id':<22} {'score':>7} {'band':<22} {'cov':>3}  label")
    for r in summary_rows:
        unsafe = " · UNSAFE" if r.get("unsafe") else ""
        print(
            f"{r['agent_id']:<22} "
            f"{r['score']:>7.2f} "
            f"{(r['band'] or '?') + unsafe:<22} "
            f"{r['coverage']:>3}  "
            f"{r['label']}"
        )

    print(f"\nDashboard live at: {DASHBOARD_URL}/")


class _NoopAgent:
    """Empty agent object used only to trigger server boot in the bootstrap call."""

    def invoke(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover
        return ""


if __name__ == "__main__":
    main()
