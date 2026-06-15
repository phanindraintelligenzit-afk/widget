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
        "NOT on the raw tool data \u2014 the tool data is ground truth. "
        "Score accuracy from 0.0 (analysis is mostly wrong or contradicts the data) "
        "to 1.0 (analysis accurately reflects the data and makes sound conclusions). "
        "Respond with a single line: SCORE: <number between 0 and 1>."
    ),
    "consistency": (
        "You are a quality evaluator measuring internal consistency. "
        "Given the outputs an AI agent produced in one run (which may include "
        "raw tool results and a final analysis), evaluate whether the final "
        "analysis is logically consistent \u2014 no contradictions, "
        "coherent reasoning, conclusions that follow from the data. "
        "Score 0.0 (many contradictions) to 1.0 (fully consistent). "
        "Respond with a single line: SCORE: <number between 0 and 1>."
    ),
}

# Hallucination prompt when source data IS available (the meaningful path).
# {source_block} is replaced with the labelled source data at eval time.
_HALLUCINATION_PROMPT_WITH_SOURCE = (
    "You are a quality evaluator measuring hallucination rate for an AI agent.\n"
    "Below is the CONTEXT the agent was given (input task + any retrieved / tool data),"
    " followed by the agent's OUTPUT.\n\n"
    "=== CONTEXT (ground truth the agent had access to) ===\n"
    "{source_block}\n\n"
    "=== AGENT OUTPUT ===\n"
    "{output_block}\n\n"
    "Estimate what fraction of SPECIFIC FACTUAL CLAIMS in the agent's output are NOT "
    "grounded in \u2014 or directly contradict \u2014 the above context.\n"
    "\u2022 General knowledge claims (widely-known facts) that match the context count as grounded.\n"
    "\u2022 Only flag claims about specific details that contradict or have no basis in the provided context.\n"
    "\u2022 0.0 = all claims grounded in the context.\n"
    "\u2022 1.0 = the output is entirely fabricated / contradicts the source.\n"
    "Respond with exactly one line: SCORE: <number between 0 and 1>"
)

# Fallback hallucination prompt when NO source data was captured.
# The LLM can only do a general plausibility check \u2014 less precise.
_HALLUCINATION_PROMPT_NO_SOURCE = (
    "You are a quality evaluator measuring hallucination rate for an AI agent.\n"
    "You have ONLY the agent's output \u2014 no original source data was captured.\n"
    "Assess whether the output contains internally inconsistent, implausible, or "
    "self-contradicting factual claims that are likely to be fabricated.\n"
    "\u2022 0.0 = output appears internally consistent and plausible (low hallucination risk).\n"
    "\u2022 1.0 = output contains many implausible or self-contradicting claims.\n"
    "NOTE: Without ground-truth source data this score is a rough estimate only.\n"
    "Respond with exactly one line: SCORE: <number between 0 and 1>\n\n"
    "Agent output:\n\n{output_block}"
)


class QState(TypedDict, total=False):
    """LangGraph state. The three scoring nodes write their slots;
    ``_outputs``, ``_llm``, and ``_source_data`` are inputs set by
    ``evaluate_quality``.

    Note: the internal key is ``hallucination`` (matching ``_PROMPTS`` and
    ``_NODE_ORDER``); it is mapped to ``QResult.hallucination_rate`` at the
    end of ``evaluate_quality``.
    """

    _outputs: list[str]
    _llm: Any  # ChatBedrockConverse instance
    _source_data: list[str]  # ground-truth context for hallucination scoring
    accuracy: Optional[float]
    consistency: Optional[float]
    hallucination: Optional[float]  # internal name; see note above
    error: Optional[str]


@dataclass
class QResult:
    accuracy: float
    consistency: float
    hallucination_rate: float
    source: str  # "llm" or "heuristic"


def evaluate_quality(
    outputs: list[str],
    *,
    source_data: list[str] | None = None,
    timeout: float = 60.0,
) -> QResult:
    """Run the LangGraph evaluator over a set of agent outputs.

    Args:
        outputs:     Agent output texts (final answers/analyses).
        source_data: The input task + retrieved docs the agent had access to.
                     When supplied, the hallucination node cross-references
                     the agent's claims against this context for a meaningful
                     score. When None, a general plausibility check is used.
        timeout:     Per-graph call timeout in seconds.

    Synchronous \u2014 wraps the async LLM calls in ``asyncio.run``. Falls
    back to the deterministic heuristic if anything goes wrong.
    """
    if not outputs:
        return QResult(0.5, 1.0, 0.5, source="heuristic")

    # Try the LLM path first; the heuristic is the safety net.
    try:
        llm = _build_llm()
    except Exception as e:  # pragma: no cover - depends on env
        _log.error(
            "Q-eval: LLM init failed (%s: %s) — falling back to heuristic. "
            "Check that AWS credentials and MODEL_NAME/BEDROCK_MODEL_ID are set.",
            type(e).__name__, e,
        )
        return _heuristic_result(outputs)

    try:
        state = _invoke_graph(outputs, llm, source_data=source_data or [], timeout=timeout)
    except Exception as e:  # pragma: no cover - network/HTTP errors
        _log.error(
            "Q-eval: LLM graph invocation failed (%s: %s) — falling back to heuristic.",
            type(e).__name__, e,
        )
        return _heuristic_result(outputs)

    if state.get("error") or state.get("accuracy") is None:
        _log.error(
            "Q-eval: LLM returned no parseable score (error=%s) — falling back to heuristic.",
            state.get("error"),
        )
        return _heuristic_result(outputs)

    return QResult(
        accuracy=float(state["accuracy"]),
        # Use explicit None check instead of `or` — a score of 0.0 is valid
        # and falsy, so `state["consistency"] or 1.0` would wrongly return 1.0.
        consistency=float(state["consistency"] if state["consistency"] is not None else 1.0),
        # "hallucination" is the internal state key; QResult calls it hallucination_rate.
        hallucination_rate=float(state["hallucination"] if state.get("hallucination") is not None else 0.5),
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
    """Build a ChatBedrockConverse from env config.

    Calls ``load_dotenv()`` as a safety net so credentials are available
    even when the caller (e.g. an atexit finalizer, a bare script, or a
    direct API ingest) did not call it themselves. ``find_dotenv()`` walks
    up from CWD so this works regardless of where Python is invoked.
    """
    try:
        from dotenv import find_dotenv, load_dotenv as _load_dotenv
        _env_file = find_dotenv(usecwd=True)
        if _env_file:
            _load_dotenv(_env_file, override=False)  # override=False: respect already-set vars
            _log.debug("Q-eval: loaded credentials from %s", _env_file)
        else:
            _log.debug("Q-eval: no .env file found; relying on system environment")
    except ImportError:
        pass  # python-dotenv not installed; rely on the system environment

    from langchain_aws import ChatBedrockConverse

    model_id = (
        os.environ.get("MODEL_NAME")
        or os.environ.get("BEDROCK_MODEL_ID")
        or "us.amazon.nova-pro-v1:0"
    )
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    _log.debug("Q-eval: building LLM model_id=%s region=%s", model_id, region)
    kwargs: dict[str, Any] = {"model_id": model_id}
    if region:
        kwargs["region_name"] = region
    return ChatBedrockConverse(**kwargs)


# ---------------------------------------------------------------------------
# LangGraph graph — three nodes, one transition each
# ---------------------------------------------------------------------------

_NODE_ORDER: tuple[str, ...] = ("accuracy", "consistency", "hallucination")
# ^^^ Must match the keys in _PROMPTS and QState. "hallucination" (not
# "hallucination_rate") is used internally so the node dict, QState field,
# and _PROMPTS lookup all agree. evaluate_quality maps it to
# QResult.hallucination_rate at the boundary.


def _scoring_node(metric: str):
    """Factory: build a LangGraph node that scores one metric."""
    def node(state: QState) -> dict:
        llm = state["_llm"]
        outputs: list[str] = state.get("_outputs") or []
        if not outputs:
            return {metric: 0.0}

        joined_outputs = "\n\n---\n\n".join(_truncate(o) for o in outputs)

        if metric == "hallucination":
            # Build a context-aware prompt when source data is available.
            source_data: list[str] = state.get("_source_data") or []
            if source_data:
                source_block = "\n\n".join(source_data)
                user_msg = _HALLUCINATION_PROMPT_WITH_SOURCE.format(
                    source_block=source_block,
                    output_block=joined_outputs,
                )
                _log.debug(
                    "Q-eval hallucination: using source-context prompt "
                    "(%d source items, %d outputs)",
                    len(source_data), len(outputs),
                )
            else:
                user_msg = _HALLUCINATION_PROMPT_NO_SOURCE.format(
                    output_block=joined_outputs,
                )
                _log.debug(
                    "Q-eval hallucination: no source data captured; "
                    "using general plausibility prompt"
                )
        else:
            prompt = _PROMPTS[metric]
            user_msg = (
                f"{prompt}\n\n"
                f"Outputs to evaluate ({len(outputs)} total):\n\n{joined_outputs}"
            )

        try:
            response = llm.invoke(user_msg)
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
    # All three keys match QState fields and _PROMPTS keys.
    g.set_entry_point("accuracy")
    g.add_edge("accuracy", "consistency")
    g.add_edge("consistency", "hallucination")
    g.add_edge("hallucination", END)
    return g.compile()


_GRAPH = None  # reset so the fixed graph is compiled on next call


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


def _invoke_graph(
    outputs: list[str],
    llm: Any,
    *,
    source_data: list[str],
    timeout: float,
) -> QState:
    initial: QState = {
        "_outputs": outputs,
        "_llm": llm,
        "_source_data": source_data,
        "accuracy": None,
        "consistency": None,
        "hallucination": None,   # matches QState key and _NODE_ORDER entry
        "error": None,
    }
    return _graph().invoke(initial)


# ---------------------------------------------------------------------------
# Parsing helpers — defensive on purpose; the LLM is creative.
# ---------------------------------------------------------------------------

# Regexes accept numbers in the full 0–100 range since LLMs sometimes
# respond on a percentage scale despite instructions. Values > 1 are
# normalised by dividing by 100 in _parse_score().
_SCORE_RE = re.compile(r"SCORE\s*[:=]\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_FALLBACK_NUMBER_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")


def _extract_text(response: Any) -> str:
    # LangChain messages have ``.content``; raw dicts have it too. We
    # accept either so tests can pass either shape.
    if hasattr(response, "content"):
        return str(response.content)
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)


def _parse_score(text: str) -> Optional[float]:
    """Parse a score from LLM text. Normalises 0–100 integer responses to
    [0, 1]. Returns None if no valid number is found."""
    if not text:
        return None

    def _normalise(v: float) -> Optional[float]:
        """Map to [0, 1]; reject values outside [0, 100]."""
        if v < 0 or v > 100:
            return None
        return min(1.0, v / 100.0 if v > 1.0 else v)

    m = _SCORE_RE.search(text)
    if m:
        return _normalise(float(m.group(1)))
    # Fall back to the first number in range [0, 100] we can find.
    for m in _FALLBACK_NUMBER_RE.finditer(text):
        v = float(m.group(1))
        result = _normalise(v)
        if result is not None:
            return result
    return None


def _truncate(text: str, limit: int = 2500) -> str:
    """Cap each output's contribution to the LLM prompt. Raised from 1500
    to 2500 so a full Markdown analysis report is sent without truncation
    on typical runs. The last `limit` characters are kept so the LLM sees
    the conclusion rather than just the preamble."""
    if len(text) <= limit:
        return text
    # Keep the TAIL of the text (the conclusion), not the head.
    return "[...truncated for length...]\n\n" + text[-(limit - 60):]
