"""LangGraph research agent — instrumented with ``dpi_ls.monitor``.

Run::

    uv run examples/langgraph_research.py

The dashboard at http://localhost:8000 populates one row for
``agent_id="langgraph-research"`` once the script exits.

What this exercises
-------------------

* ``LangGraphPatcher`` (from ``dpi_ls/frameworks/langgraph.py``) wraps
  ``graph.ainvoke`` so the collector observes the run as one
  ``agent_runs_completed += 1`` (drives **P**).
* Inside the graph node, we call ``record_llm_call`` with the
  LangChain AIMessage's ``usage_metadata`` so the **C** (Cost) dimension
  picks up real token counts — ``LangGraphPatcher`` itself only
  captures text, not tokens, because the LLM call is one level deeper
  than ``ainvoke``.
* The final answer is a clean Markdown report with ``##`` headers so
  the deterministic V / G / R scanners all see the output as
  structured, governance-clean, and incident-free.
* The LangGraph Q evaluator inside ``dpi_ls`` scores the output
  against the data the agent saw (Q dimension).
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(override=True)

import dpi_ls
from dpi_ls import _state


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------
class ResearchState(TypedDict, total=False):
    question: str
    final_answer: str
    tokens_in: int
    tokens_out: int


# ---------------------------------------------------------------------------
# Node: ask Bedrock for a structured Markdown summary.
# ---------------------------------------------------------------------------
def _build_llm() -> ChatBedrockConverse:
    model_id = os.environ["BEDROCK_MODEL_ID"]
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    kwargs: dict[str, Any] = {"model_id": model_id}
    if region:
        kwargs["region_name"] = region
    return ChatBedrockConverse(**kwargs)


async def _research_node(state: ResearchState) -> ResearchState:
    llm = _build_llm()
    system = SystemMessage(
        content=(
            "You are a research summarizer. Produce a short, structured "
            "Markdown report with at least two '##' section headers. "
            "Keep the answer under 400 words. Do not include any email "
            "addresses, phone numbers, or API keys."
        )
    )
    user = HumanMessage(content=state["question"])
    response = await llm.ainvoke([system, user])

    # Manually push tokens + cost into the active collector so the C
    # dimension reflects real usage. LangGraphPatcher wraps the
    # *graph* entry point — it does not see the inner LLM call.
    usage = getattr(response, "usage_metadata", None) or {}
    in_t = int(usage.get("input_tokens") or 0)
    out_t = int(usage.get("output_tokens") or 0)
    text = response.content if isinstance(response.content, str) else str(response.content)
    cost = (in_t + out_t) * 0.000001  # $0.001 / 1k tokens blended

    collector = _state.get_collector()
    if collector is not None:
        collector.record_llm_call(
            text,
            tokens_in=in_t,
            tokens_out=out_t,
            cost=cost,
            ok=True,
        )

    return {
        "final_answer": text,
        "tokens_in": in_t,
        "tokens_out": out_t,
    }


def _build_graph():
    from langgraph.graph import END, StateGraph

    g = StateGraph(ResearchState)
    g.add_node("research", _research_node)
    g.set_entry_point("research")
    g.add_edge("research", END)
    return g.compile()


async def main() -> None:
    graph = _build_graph()
    # human_baseline=1: this agent emits one report per run, matching
    # one human analyst who would also produce one report.
    dpi_ls.monitor(
        graph,
        agent_id="langgraph-research",
        agent_name="LangGraph Research Agent",
        human_baseline=1,
    )

    question = (
        "Summarize the three biggest risks of deploying AI agents in "
        "regulated industries (finance, healthcare) and the controls that "
        "mitigate each risk. Use Markdown section headers."
    )
    result = await graph.ainvoke({"question": question})

    answer = result.get("final_answer", "")
    # Trim to ASCII so the demo prints cleanly on Windows cp1252 consoles.
    print("\n--- LangGraph Final Output ---")
    print(answer.encode("ascii", errors="ignore").decode("ascii"))
    print(
        f"\ntokens: in={result.get('tokens_in', 0)}  out={result.get('tokens_out', 0)}"
    )


if __name__ == "__main__":
    # DPI_LS_NO_BLOCK=1 in .env (or here) skips the "press Enter" pause so
    # the script exits cleanly under CI / orchestrator runs.
    os.environ.setdefault("DPI_LS_NO_BLOCK", "1")
    asyncio.run(main())
