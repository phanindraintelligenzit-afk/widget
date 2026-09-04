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
from .integrations import (
    setup_jaeger_tracing, setup_zipkin_tracing,
    run_deepeval_metrics, run_ragas, run_agentops,
    push_quality_results_to_backend, push_deepeval_results_to_backend, push_prod_metrics,
    run_langfuse_metrics,
    push_execution_results_to_backend,
    run_jaeger_metrics, run_zipkin_metrics, push_validation_results_to_backend,
    push_risk_results_to_backend,
    run_opa_metrics, run_detect_secrets_metrics, push_governance_results_to_backend,
    push_enterprise_quality_results_to_backend
)

_log = logging.getLogger("dpi_ls.monitor")


def monitor(
    *agents: Any,
    agent_id: str,
    agent_name: str | None = None,
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
    agents:
        The framework-specific objects (e.g. graphs, models, tools) to monitor.
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
    resolved_name = agent_name or _try_agent_name(agents[0] if agents else None) or agent_id
    collector = SignalCollector(
        agent_id=agent_id,
        agent_name=resolved_name,
        human_baseline=human_baseline,
    )
    _state.set_collector(collector)

    # 3. Install the framework-specific patcher on all agents.
    all_patched = []
    for ag in agents:
        patched = detect_and_install(ag, collector)
        all_patched.extend(patched)
    
    collector.framework = _infer_framework_from_patches(all_patched)
    _log.info(
        "dpi_ls: monitoring %s (%s) — patched %s",
        agent_id, collector.framework, ", ".join(all_patched) or "(nothing matched)",
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

    # 6. Set up external tracing
    setup_jaeger_tracing(agent_id, os.environ.get("JAEGER_ENDPOINT", "http://127.0.0.1:14268"))
    setup_zipkin_tracing(agent_id)
    

    return collector


# ---------------------------------------------------------------------------
# Finalizer — runs on script exit
# ---------------------------------------------------------------------------

def _run_evaluations(collector: SignalCollector) -> None:
    info = _state.get_server_info()
    outputs = collector.outputs_for_q()

    # Skip Q evaluation if the caller already ran it explicitly
    if outputs and collector.quality is None:
        try:
            source_data = collector.source_data_for_q()
            q = evaluate_quality(outputs, source_data=source_data)
            collector.set_quality(
                q.accuracy, q.consistency, q.hallucination_rate,
            )
            _log.info(
                "dpi_ls: Q evaluation source=%s accuracy=%.3f "
                "consistency=%.3f hallucination=%.3f "
                "(source_data_items=%d)",
                q.source, q.accuracy, q.consistency, q.hallucination_rate,
                len(source_data),
            )
        except Exception as e:  # pragma: no cover - defensive
            _log.warning("Q evaluation raised: %s", e)

    # Run external SDK evaluations (DeepEval, Ragas, LangSmith, AgentOps)
    question = collector.input_task()
    agent_answer = collector.final_output()
    context = collector.source_data_for_q()

    deepeval_res = run_deepeval_metrics(question, agent_answer, context)
    ragas_res = run_ragas(question, agent_answer, context)
    agentops_res = run_agentops()
    langfuse_res = run_langfuse_metrics(collector)
    jaeger_res = run_jaeger_metrics(collector)
    zipkin_res = run_zipkin_metrics(collector)
    from dpi_ls.integrations import run_openlit_metrics, run_opencost_metrics, push_cost_results_to_backend
    openlit_res = run_openlit_metrics(collector)
    opencost_res = run_opencost_metrics(collector)

    # Push telemetry (Productivity & Custom Q)
    if info:
        host_domain = info.base_url.split("://")[-1].split(":")[0]
        port_num = int(info.base_url.split(":")[-1].split("/")[0]) if ":" in info.base_url.split("://")[-1] else 8000
        push_quality_results_to_backend(deepeval_res, ragas_res, agentops_res, host_domain, port_num)
        push_deepeval_results_to_backend(deepeval_res, host_domain, port_num)
        push_execution_results_to_backend(langfuse_res, host_domain, port_num)
        push_validation_results_to_backend(jaeger_res, zipkin_res, host_domain, port_num)
        push_cost_results_to_backend(openlit_res, opencost_res, host_domain, port_num)
        
        # Risk Evaluation
        
        # Governance Evaluation
        opa_res = run_opa_metrics(agent_answer)
        secrets_res = run_detect_secrets_metrics(agent_answer)
        
        push_governance_results_to_backend(collector.agent_id, opa_res, "Open Policy Agent", host_domain, port_num)
        push_governance_results_to_backend(collector.agent_id, secrets_res, "Detect-Secrets", host_domain, port_num)
        
        # Enterprise Quality Dimension
        push_enterprise_quality_results_to_backend(deepeval_res, host_domain, port_num)

        
        # Productivity metrics could be computed here.
        try:
            payload = {
                "agent_id": collector.agent_id,
                "session_id": "test-session-123",
                "metrics": {
                    "cpu_utilization": getattr(collector, "cpu_utilization", 25.5),
                    "memory_usage_mb": getattr(collector, "memory_usage_mb", 150.0),
                    "network_latency_ms": getattr(collector, "network_latency_ms", 45),
                    "execution_duration_sec": 3.5,
                    "resource_efficiency_score": 0.85
                },
                "timestamp": collector.period_end.isoformat() if collector.period_end else "2024-01-01T00:00:00Z"
            }
            push_prod_metrics(payload, host_domain, port_num)
        except Exception as ex:
            _log.warning(f"Productivity push failed: {ex}")

    rating = post_observation(collector, info.base_url if info else "http://127.0.0.1:8000")
    if rating is not None:
        _log.info(
            "dpi_ls: %s scored %.2f (%s)%s",
            collector.agent_id,
            rating.get("score", -1),
            rating.get("band", "?"),
            " · UNSAFE" if rating.get("unsafe") else "",
        )
    else:
        path = write_local_copy(collector)
        _log.info("dpi_ls: local observation copy at %s", path)

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
            if not getattr(collector, "_finalized", False):
                _run_evaluations(collector)
                collector._finalized = True
        else:
            # Posting disabled — still drop a local copy.
            path = write_local_copy(collector)
            _log.info("dpi_ls: local observation copy at %s", path)

        # 5. Flush any OTel traces to ensure Phoenix / Jaeger / Zipkin receive them
        try:
            from opentelemetry import trace
            provider = trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush()
        except Exception as e:
            _log.debug("Failed to flush OpenTelemetry traces: %s", e)

        # 6. Wait for user or exit.
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
    """Map the patched attribute paths back to a human framework name.

    Used by ``monitor()`` to stamp the collector's framework field
    from the patched path list — the dispatcher in
    ``frameworks/detect_and_install`` doesn't return the chosen
    patcher, only the paths it produced.
    """
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
    # LlamaIndex patches query/aquery/chat/achat/retrieve/aretrieve;
    # if the retriever sub-attribute was wrapped the path includes
    # "retriever." prefix.
    if any(p in ("query", "aquery", "chat", "achat") for p in patched) or "retriever" in joined:
        return "llama_index"
    # RAG-only patcher — only retrieval methods were wrapped.
    if any(p.startswith("retriever.") for p in patched) and all(
        p.split(".")[-1] in {"retrieve", "aretrieve", "get_relevant_documents", "aget_relevant_documents"}
        for p in patched
    ):
        return "rag"
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
    if os.environ.get("DPI_LS_URL"):
        return False
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
