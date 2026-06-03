"""Compute the 7 normalized [0,1] sub-metrics from an AgentObservation.

Pure functions. No I/O. The only contract dependency is AgentObservation +
Settings + AgentBaseline.
"""
from __future__ import annotations

from typing import Optional

from contract import AgentBaseline, AgentObservation, PartialObservation, Settings


def compute_P(ai_output_per_period: float, human_baseline: float) -> float:
    if human_baseline <= 0:
        return 0.0
    return min(1.0, ai_output_per_period / human_baseline)


def compute_Q(
    accuracy: float,
    consistency: float,
    hallucination_rate: float,
    sub_weights: dict[str, float],
) -> float:
    return (
        sub_weights["accuracy"] * accuracy
        + sub_weights["consistency"] * consistency
        + sub_weights["hallucination"] * (1.0 - hallucination_rate)
    )


def compute_E(successful: int, attempts: int) -> float:
    if attempts <= 0:
        return 0.0
    return successful / attempts


def compute_G(violations: int, total_actions: int) -> float:
    if total_actions <= 0:
        # No actions taken → vacuously compliant. Engine still scores it,
        # gates still apply on the floor value (1.0 here passes).
        return 1.0
    return 1.0 - (violations / total_actions)


def compute_R(incidents: list, r_max: float) -> float:
    if r_max <= 0:
        return 0.0
    total = 0.0
    for inc in incidents:
        # Accept both Pydantic models and plain dicts (for fixtures/tests).
        freq = getattr(inc, "frequency", None)
        sev = getattr(inc, "severity_weight", None)
        if freq is None:
            freq = inc["frequency"]
            sev = inc["severity_weight"]
        total += freq * sev
    return 1.0 - min(1.0, total / r_max)


def compute_V(validated: int, required: int) -> float:
    if required <= 0:
        return 1.0
    return validated / required


def compute_C(
    human_cost_per_output: float,
    ai_cost_per_output: float,
    utilization: float,
) -> float:
    if ai_cost_per_output <= 0:
        return 0.0
    ratio = min(1.0, human_cost_per_output / ai_cost_per_output)
    return ratio * utilization


def metrics_from_observation(
    obs: AgentObservation,
    settings: Settings,
    baseline: AgentBaseline,
) -> dict[str, Optional[float]]:
    """Bridge from canonical observation to the 7 normalized metrics.

    Quality may come back as None when the observation lacks it — that's a
    signal to defer Q to a conversational/SME capture, not a zero.
    """
    P = compute_P(obs.tasks.completed, baseline.human_output_per_period)

    if obs.quality is None:
        Q: Optional[float] = None
    else:
        Q = compute_Q(
            obs.quality.accuracy,
            obs.quality.consistency,
            obs.quality.hallucination_rate,
            settings.q_sub_weights,
        )

    E = compute_E(obs.executions.successful, obs.executions.attempts)
    G = compute_G(len(obs.policy.violations), obs.policy.total_actions)
    R = compute_R(obs.incidents, settings.r_max)
    V = compute_V(obs.validation.validated_components, obs.validation.required_components)
    C = compute_C(
        settings.human_cost_per_output,
        obs.cost.ai_cost_per_output,
        settings.utilization,
    )

    return {"P": P, "Q": Q, "E": E, "G": G, "R": R, "V": V, "C": C}


def metrics_from_partial(
    partial: PartialObservation,
    settings: Settings,
    baseline: AgentBaseline,
) -> dict[str, Optional[float]]:
    """Compute metrics from a partial. Dimensions never supplied stay None.

    The engine's composite redistributes weight away from None metrics,
    so a fresh agent with only a Cost partial gets a C-dominated score
    (rather than zeros pulling everything down).
    """
    P = (
        compute_P(partial.tasks.completed, baseline.human_output_per_period)
        if partial.tasks is not None
        else None
    )
    Q = (
        compute_Q(
            partial.quality.accuracy,
            partial.quality.consistency,
            partial.quality.hallucination_rate,
            settings.q_sub_weights,
        )
        if partial.quality is not None
        else None
    )
    E = (
        compute_E(partial.executions.successful, partial.executions.attempts)
        if partial.executions is not None
        else None
    )
    G = (
        compute_G(len(partial.policy.violations), partial.policy.total_actions)
        if partial.policy is not None
        else None
    )
    R = (
        compute_R(partial.incidents, settings.r_max)
        if partial.incidents is not None
        else None
    )
    V = (
        compute_V(partial.validation.validated_components, partial.validation.required_components)
        if partial.validation is not None
        else None
    )
    C = (
        compute_C(
            settings.human_cost_per_output,
            partial.cost.ai_cost_per_output,
            settings.utilization,
        )
        if partial.cost is not None
        else None
    )
    return {"P": P, "Q": Q, "E": E, "G": G, "R": R, "V": V, "C": C}
