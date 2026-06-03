"""SME / QA conversational quality capture.

A tiny linear state machine that walks an SME through three questions —
accuracy, consistency, hallucination rate — then a confirm step.
Pure: no I/O, no DB. The API persists the session between turns; this
module advances it one step per call.

The state shape is deliberately small and explicit so swapping the
runner for a LangGraph graph later is mechanical — same fields, same
transitions, just a graph executor on top.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Step identifiers — also surfaced to the UI so it can render the right field.
STEP_ASK_ACCURACY = "ask_accuracy"
STEP_ASK_CONSISTENCY = "ask_consistency"
STEP_ASK_HALLUCINATION = "ask_hallucination"
STEP_REVIEW = "review"
STEP_DONE = "done"

_ORDER = (
    STEP_ASK_ACCURACY,
    STEP_ASK_CONSISTENCY,
    STEP_ASK_HALLUCINATION,
    STEP_REVIEW,
    STEP_DONE,
)

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
    error: Optional[str] = None  # transient, cleared on next advance
    history: list[dict] = field(default_factory=list)


class SMEFlowError(ValueError):
    pass


def start(agent_id: str, submitted_by: str) -> SMEFlowState:
    if not agent_id:
        raise SMEFlowError("agent_id is required")
    if not submitted_by:
        raise SMEFlowError("submitted_by is required")
    return SMEFlowState(agent_id=agent_id, submitted_by=submitted_by)


def _parse_unit(raw: str) -> float:
    """Accept '93', '0.93', '93%', '  0.93 '. Map to [0, 1]."""
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
        raise SMEFlowError("value must be between 0 and 100")
    return v


def advance(state: SMEFlowState, response: str) -> SMEFlowState:
    """Apply one user response. Mutates and returns state."""
    state.error = None
    state.history.append({"step": state.step, "response": response})

    try:
        if state.step == STEP_ASK_ACCURACY:
            state.accuracy = _parse_unit(response)
            state.step = STEP_ASK_CONSISTENCY
        elif state.step == STEP_ASK_CONSISTENCY:
            state.consistency = _parse_unit(response)
            state.step = STEP_ASK_HALLUCINATION
        elif state.step == STEP_ASK_HALLUCINATION:
            state.hallucination_rate = _parse_unit(response)
            state.step = STEP_REVIEW
        elif state.step == STEP_REVIEW:
            answer = (response or "").strip().lower()
            if answer in ("y", "yes"):
                state.step = STEP_DONE
            elif answer in ("n", "no"):
                state.aborted = True
                state.step = STEP_DONE
            else:
                raise SMEFlowError("please reply 'yes' or 'no'")
        elif state.step == STEP_DONE:
            raise SMEFlowError("session already complete")
        else:
            raise SMEFlowError(f"unknown step '{state.step}'")
    except SMEFlowError as e:
        state.error = str(e)
        # On error, undo the history entry and stay on the same step.
        state.history.pop()
    return state


def current_prompt(state: SMEFlowState) -> str:
    return PROMPTS[state.step]


def review_summary(state: SMEFlowState) -> dict[str, Optional[float]]:
    return {
        "accuracy": state.accuracy,
        "consistency": state.consistency,
        "hallucination_rate": state.hallucination_rate,
    }


def is_complete(state: SMEFlowState) -> bool:
    return state.step == STEP_DONE


def is_committed(state: SMEFlowState) -> bool:
    """True when the user said yes at REVIEW — i.e. ratings should persist."""
    return state.step == STEP_DONE and not state.aborted