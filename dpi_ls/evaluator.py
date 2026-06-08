"""LangGraph-based Q-dimension evaluator.

Spec: use a LangGraph StateGraph with three LLM scoring nodes
(accuracy, consistency, hallucination). The graph is compiled lazily
the first time ``evaluate_quality()`` runs and reused across calls.

LLM: AWS Bedrock via ``langchain_aws.ChatBedrockConverse`` — model id
read from ``MODEL_NAME`` env var (or ``BEDROCK_MODEL_ID`` as a fallback).
AWS credentials are picked up from the standard boto3 chain.

If the LLM cannot be reached for any reason, we fall back to a
deterministic text heuristic (see ``heuristics.py``) and emit a
warning. The collector still gets a Q triple either way — it's
better to have a rough Q than no Q at all, and the engine's coverage
cap protects against low-confidence heuristic scores.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from .heuristics import heuristic_quality

_log = logging.getLogger("dpi_ls.evaluator")

# Maps to "Exceptional" in human-readable terms — but the LLM is asked
# for a plain 0–1 number and we parse strictly. Loose prompt, strict
# parse.
_PROMPTS: dict[str, str] = {
    "accuracy": (
        "You are a quality evaluator for an AI agent. "
        "You will receive the outputs the agent produced during one run. "
        "These may include raw data from tool calls (e.g. JSON API responses) "
        "followed by the agent's final analysis or answer. "
        "Focus your evaluation on the agent's analysis and recommendations, "
        "NOT on the raw tool data — the tool data is ground truth. "
        "Score accuracy from 0.0 (analysis is mostly wrong or contradicts the data) "
        "to 1.0 (analysis accurately reflects the data and makes sound conclusions). "
        "Respond with a single line: SCORE: <number between 0 and 1>."
    ),
    "consistency": (
        "You are a quality evaluator measuring internal consistency. "
        "Given the outputs an AI agent produced in one run (which may include "
        "raw tool results and a final analysis), evaluate whether the final "
        "analysis is logically consistent — no contradictions, "
        "coherent reasoning, conclusions that follow from the data. "
        "Score 0.0 (many contradictions) to 1.0 (fully consistent). "
        "Respond with a single line: SCORE: <number between 0 and 1>."
    ),
    "hallucination": (
        "You are a quality evaluator measuring hallucination rate. "
        "Given the outputs an AI agent produced (tool results + final analysis), "
        "estimate what fraction of statements in the FINAL ANALYSIS are fabricated — "
        "i.e., claims NOT supported by the tool data provided. "
        "0.0 = no hallucinations (everything is grounded in the data), "
        "1.0 = everything is fabricated. "
        "Note: reasonable interpretations and recommendations based on the data "
        "are NOT hallucinations. Only flag claims that directly contradict or "
        "have no basis in the provided data. "
        "Respond with a single line: SCORE: <number between 0 and 1>."
    ),
}


class QState(TypedDict, total=False):
    """LangGraph state. The three scoring nodes write their slots;
    ``_outputs`` and ``_llm`` are inputs set by ``evaluate_quality``."""

    _outputs: list[str]
    _llm: Any  # ChatBedrockConverse instance
    accuracy: Optional[float]
    consistency: Optional[float]
    hallucination_rate: Optional[float]
    error: Optional[str]


@dataclass
class QResult:
    accuracy: float
    consistency: float
    hallucination_rate: float
    source: str  # "llm" or "heuristic"


def evaluate_quality(outputs: list[str], *, timeout: float = 60.0) -> QResult:
    """Run the LangGraph evaluator over a set of agent outputs.

    Synchronous — wraps the async LLM calls in ``asyncio.run``. Falls
    back to the deterministic heuristic if anything goes wrong.
    """
    if not outputs:
        return QResult(0.0, 1.0, 0.5, source="heuristic")

    # Try the LLM path first; the heuristic is the safety net.
    try:
        llm = _build_llm()
    except Exception as e:  # pragma: no cover - depends on env
        _log.warning("LLM init failed (%s); using heuristic Q.", e)
        return _heuristic_result(outputs)

    try:
        # The LangGraph graph is async-friendly; asyncio.run gives us a
        # clean event loop even when the user's main code is sync.
        state = asyncio.run(_invoke_graph(outputs, llm, timeout=timeout))
    except Exception as e:  # pragma: no cover - network/HTTP errors
        _log.warning("LLM evaluation failed (%s); using heuristic Q.", e)
        return _heuristic_result(outputs)

    if state.get("error") or state.get("accuracy") is None:
        _log.warning(
            "LLM evaluation returned no score (error=%s); using heuristic Q.",
            state.get("error"),
        )
        return _heuristic_result(outputs)

    return QResult(
        accuracy=float(state["accuracy"]),
        # Use explicit None check instead of `or` — a score of 0.0 is valid
        # and falsy, so `state["consistency"] or 1.0` would wrongly return 1.0.
        consistency=float(state["consistency"] if state["consistency"] is not None else 1.0),
        hallucination_rate=float(state["hallucination_rate"] if state["hallucination_rate"] is not None else 0.5),
        source="llm",
    )


def _heuristic_result(outputs: list[str]) -> QResult:
    h = heuristic_quality(outputs)
    return QResult(
        accuracy=h["accuracy"],
        consistency=h["consistency"],
        hallucination_rate=h["hallucination_rate"],
        source="heuristic",
    )


# ---------------------------------------------------------------------------
# LLM construction
# ---------------------------------------------------------------------------

def _build_llm():  # pragma: no cover - depends on env
    """Build a ChatBedrockConverse from env config. No boto3 auth is
    configured here — the Bedrock SDK picks up credentials from the
    standard AWS env / IAM role / SSO chain."""
    from langchain_aws import ChatBedrockConverse

    model_id = (
        os.environ.get("MODEL_NAME")
        or os.environ.get("BEDROCK_MODEL_ID")
        or "us.amazon.nova-pro-v1:0"
    )
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    kwargs: dict[str, Any] = {"model_id": model_id}
    if region:
        kwargs["region_name"] = region
    return ChatBedrockConverse(**kwargs)


# ---------------------------------------------------------------------------
# LangGraph graph — three nodes, one transition each
# ---------------------------------------------------------------------------

_NODE_ORDER: tuple[str, ...] = ("accuracy", "consistency", "hallucination")


def _scoring_node(metric: str):
    """Factory: build a LangGraph node that scores one metric."""
    async def node(state: QState) -> dict:
        llm = state["_llm"]
        outputs: list[str] = state.get("_outputs") or []
        if not outputs:
            return {metric: 0.0}
        prompt = _PROMPTS[metric]
        joined = "\n\n---\n\n".join(_truncate(o) for o in outputs)
        user_msg = (
            f"{prompt}\n\n"
            f"Outputs to evaluate ({len(outputs)} total):\n\n{joined}"
        )
        try:
            response = await llm.ainvoke(user_msg)
            text = _extract_text(response)
        except Exception as e:  # pragma: no cover - LLM call failure
            return {"error": f"{metric} node failed: {e}"}
        score = _parse_score(text)
        if score is None:
            return {"error": f"{metric}: could not parse '{text[:80]}...'"}
        return {metric: score}
    node.__name__ = f"_score_{metric}"
    return node


def _build_graph():
    """Compile the StateGraph once. Graph is stateless aside from the
    per-invocation LLM handle passed via state."""
    from langgraph.graph import END, StateGraph

    g = StateGraph(QState)
    nodes = {m: _scoring_node(m) for m in _NODE_ORDER}
    for name, fn in nodes.items():
        g.add_node(name, fn)
    # Linear chain: accuracy → consistency → hallucination → END.
    g.set_entry_point("accuracy")
    g.add_edge("accuracy", "consistency")
    g.add_edge("consistency", "hallucination")
    g.add_edge("hallucination", END)
    return g.compile()


_GRAPH = None


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


async def _invoke_graph(outputs: list[str], llm, *, timeout: float) -> QState:
    initial: QState = {
        "_outputs": outputs,
        "_llm": llm,
        "accuracy": None,
        "consistency": None,
        "hallucination_rate": None,
        "error": None,
    }
    coro = _graph().ainvoke(initial)
    return await asyncio.wait_for(coro, timeout=timeout)


# ---------------------------------------------------------------------------
# Parsing helpers — defensive on purpose; the LLM is creative.
# ---------------------------------------------------------------------------

_SCORE_RE = re.compile(r"SCORE\s*[:=]\s*([0-1](?:\.\d+)?)", re.IGNORECASE)
_FALLBACK_NUMBER_RE = re.compile(r"\b([0-1](?:\.\d+)?)\b")


def _extract_text(response: Any) -> str:
    # LangChain messages have ``.content``; raw dicts have it too. We
    # accept either so tests can pass either shape.
    if hasattr(response, "content"):
        return str(response.content)
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)


def _parse_score(text: str) -> Optional[float]:
    if not text:
        return None
    m = _SCORE_RE.search(text)
    if m:
        return float(m.group(1))
    # Fall back to the first 0–1 number we can find.
    m = _FALLBACK_NUMBER_RE.search(text)
    if m:
        return float(m.group(1))
    return None


def _truncate(text: str, limit: int = 2500) -> str:
    """Cap each output's contribution to the LLM prompt. Raised from 1500
    to 2500 so a full Markdown analysis report is sent without truncation
    on typical runs. The last `limit` characters are kept so the LLM sees
    the conclusion rather than just the preamble."""
    if len(text) <= limit:
        return text
    return text[: limit - 60] + "\n\n[...truncated for length...]"
