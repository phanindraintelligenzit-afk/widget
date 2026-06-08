"""SME conversational quality capture — LangGraph StateGraph.

Linear flow: ask_accuracy → ask_consistency → ask_hallucination → review →
done. Each turn (API call) invokes the graph for exactly one transition.

The public surface — SMEFlowState dataclass, start(), advance(),
current_prompt(), review_summary(), is_complete(), is_committed(),
the STEP_* constants and PROMPTS dict — is unchanged from the
hand-rolled M6 version. The graph is an implementation detail of
advance(); callers and tests don't see it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph


# ---- Step identifiers + prompts (public) ---------------------------------

STEP_ASK_ACCURACY = "ask_accuracy"
STEP_ASK_CONSISTENCY = "ask_consistency"
STEP_ASK_HALLUCINATION = "ask_hallucination"
STEP_REVIEW = "review"
STEP_DONE = "done"

PROMPTS: dict[str, str] = {
    STEP_ASK_ACCURACY: (
        "On a 0–100 scale, how often did the agent produce correct outputs "
        "in this period?"
    ),
    STEP_ASK_CONSISTENCY: (
        "How consistent were the outputs across similar inputs (0–100)?"
    ),
    STEP_ASK_HALLUCINATION: (
        "What fraction of outputs contained hallucinated facts (0–100)? "
        "Lower is better."
    ),
    STEP_REVIEW: "Submit these ratings? (yes / no)",
    STEP_DONE: "Captured — Q will be reflected on the next score.",
}


@dataclass
class SMEFlowState:
    agent_id: str
    submitted_by: str
    step: str = STEP_ASK_ACCURACY
    accuracy: Optional[float] = None
    consistency: Optional[float] = None
    hallucination_rate: Optional[float] = None
    aborted: bool = False
    error: Optional[str] = None
    history: list[dict] = field(default_factory=list)


class SMEFlowError(ValueError):
    pass


# ---- Graph internals -----------------------------------------------------

class _Graph(TypedDict, total=False):
    """TypedDict projection of SMEFlowState used by the StateGraph.

    Identical fields, plus a transient ``_response`` set by advance() before
    invoking and stripped from the returned state.
    """
    agent_id: str
    submitted_by: str
    step: str
    accuracy: Optional[float]
    consistency: Optional[float]
    hallucination_rate: Optional[float]
    aborted: bool
    error: Optional[str]
    history: list
    _response: str


def _parse_unit(raw: str) -> float:
    """Accept '93', '0.93', '93%', '  0.93 '. Map to [0, 1].

    Accepted formats:
    - Integer 0–100 (e.g. ``85``) → divided by 100.
    - Decimal 0.0–1.0 (e.g. ``0.85``) → used as-is.
    - Percentage suffix (e.g. ``85%``) → treated as integer form.
    """
    s = (raw or "").strip().rstrip("%").strip()
    if not s:
        raise SMEFlowError("empty input")
    try:
        v = float(s)
    except ValueError:
        raise SMEFlowError(f"could not parse '{raw}' as a number")
    if v > 1:
        v = v / 100.0
    if v < 0 or v > 1:
        raise SMEFlowError(
            "value must be between 0 and 100 (integer) or 0.0 and 1.0 (decimal)"
        )
    return v


def _record(state: _Graph, response: str) -> list[dict]:
    return [*state.get("history", []), {"step": state["step"], "response": response}]


def _number_node(field_name: str, next_step: str):
    """Make a node that parses a 0–100 number, sets ``field_name``, advances."""
    def node(state: _Graph) -> dict:
        resp = state.get("_response", "")
        try:
            v = _parse_unit(resp)
        except SMEFlowError as e:
            return {"error": str(e)}
        return {
            field_name: v,
            "step": next_step,
            "error": None,
            "history": _record(state, resp),
        }
    return node


def _review_node(state: _Graph) -> dict:
    resp = (state.get("_response", "") or "").strip().lower()
    if resp in ("y", "yes"):
        return {"step": STEP_DONE, "aborted": False, "error": None, "history": _record(state, resp)}
    if resp in ("n", "no"):
        return {"step": STEP_DONE, "aborted": True, "error": None, "history": _record(state, resp)}
    return {"error": "please reply 'yes' or 'no'"}


_NODES = {
    STEP_ASK_ACCURACY:      _number_node("accuracy",           STEP_ASK_CONSISTENCY),
    STEP_ASK_CONSISTENCY:   _number_node("consistency",        STEP_ASK_HALLUCINATION),
    STEP_ASK_HALLUCINATION: _number_node("hallucination_rate", STEP_REVIEW),
    STEP_REVIEW:            _review_node,
}


def _route(state: _Graph) -> str:
    step = state.get("step")
    return step if step in _NODES else END


_COMPILED = None


def _graph():
    """Compile once, reuse across requests. Graph is stateless."""
    global _COMPILED
    if _COMPILED is None:
        g = StateGraph(_Graph)
        for name, node in _NODES.items():
            g.add_node(name, node)
            g.add_edge(name, END)
        g.set_conditional_entry_point(
            _route,
            {**{name: name for name in _NODES}, END: END},
        )
        _COMPILED = g.compile()
    return _COMPILED


# ---- Public API (unchanged) ---------------------------------------------

def start(agent_id: str, submitted_by: str) -> SMEFlowState:
    if not agent_id:
        raise SMEFlowError("agent_id is required")
    if not submitted_by:
        raise SMEFlowError("submitted_by is required")
    return SMEFlowState(agent_id=agent_id, submitted_by=submitted_by)


def advance(state: SMEFlowState, response: str) -> SMEFlowState:
    """Apply one user response by routing through the StateGraph."""
    # Terminal step is outside the graph — guard here so we don't loop.
    if state.step == STEP_DONE:
        state.error = "session already complete"
        return state

    payload: dict = asdict(state)
    payload["_response"] = response
    payload["error"] = None
    new_payload = _graph().invoke(payload)
    new_payload.pop("_response", None)
    return SMEFlowState(**new_payload)


def current_prompt(state: SMEFlowState) -> str:
    """Return the prompt for the current step, or '' if the step is unknown.

    Using ``.get()`` prevents a KeyError when an unexpected step value
    (e.g. an error state set by external code) reaches this function.
    """
    return PROMPTS.get(state.step, "")


def review_summary(state: SMEFlowState) -> dict[str, Optional[float]]:
    return {
        "accuracy": state.accuracy,
        "consistency": state.consistency,
        "hallucination_rate": state.hallucination_rate,
    }


def is_complete(state: SMEFlowState) -> bool:
    return state.step == STEP_DONE


def is_committed(state: SMEFlowState) -> bool:
    return state.step == STEP_DONE and not state.aborted
