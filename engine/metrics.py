"""Compute the 7 normalized [0,1] sub-metrics from an AgentObservation.

Pure functions. No I/O. The only contract dependency is
AgentObservation + Settings + AgentBaseline.

Formulae (per the spec)
-----------------------

::

    P = min(1, AI_output_per_period / human_baseline)              (baseline from settings)
    Q = 0.7·Accuracy + 0.2·Consistency + 0.1·(1 − Hallucination)   (inputs 0–1; null → conversational)
    E = successful_executions / total_attempts
    G = 1 − (policy_violations / total_actions)
    R = 1 − min(1, Σ(freq × severity) / R_max)                     (R_max from settings)
    V = validated_components / total_required
    C = min(1, human_cost_per_output / AI_cost_per_output) × utilization

All metrics are normalised to [0,1]. None is a valid value and
means "needs input" — see :func:`metrics_from_observation` and the
SME flow for how the engine handles a missing dimension.
"""
from __future__ import annotations

from typing import Optional

from contract import AgentBaseline, AgentObservation, PartialObservation, Settings


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------

def compute_P(
    ai_output_per_period: float,
    human_baseline: float,
    normalization_factor: float = 1.0,
) -> float:
    """P = min(1, (AI_output_per_period / human_baseline) * normalization_factor).

    Output is clamped to [0, 1]. A negative ``ai_output_per_period``
    (which should never happen, but is the kind of thing a
    misconfigured adapter can send) is treated as 0, not as a
    negative metric.
    """
    if human_baseline <= 0:
        return 0.0
    if ai_output_per_period <= 0:
        return 0.0
    return min(1.0, (ai_output_per_period / human_baseline) * normalization_factor)


def compute_Q(
    accuracy: float,
    consistency: float,
    hallucination_rate: float,
    sub_weights: dict[str, float],
) -> float:
    """Q = w_acc·Accuracy + w_con·Consistency + w_hal·(1 − Hallucination).

    The default sub-weights are 0.70/0.20/0.10 (in
    :data:`contract.DEFAULT_Q_SUB_WEIGHTS`) and live in Settings so a
    deployment can re-balance accuracy vs consistency vs
    hallucination-rate without code changes.

    Output is clamped to [0, 1]. Inputs outside [0, 1] are clipped
    — the engine never produces a metric > 1.
    """
    a = max(0.0, min(1.0, accuracy))
    c = max(0.0, min(1.0, consistency))
    h = max(0.0, min(1.0, hallucination_rate))
    return max(0.0, min(
        1.0,
        sub_weights["accuracy"] * a
        + sub_weights["consistency"] * c
        + sub_weights["hallucination"] * (1.0 - h),
    ))


def compute_E(successful: int, attempts: int) -> float:
    """E = successful_executions / total_attempts.

    Output is clamped to [0, 1]. ``successful`` larger than
    ``attempts`` (an over-counted adapter) is treated as 1.0, not as
    a metric > 1.
    """
    if attempts <= 0:
        return 0.0
    if successful <= 0:
        return 0.0
    return min(1.0, successful / attempts)


def compute_G(violations: int, total_actions: int) -> float:
    """G = 1 − (policy_violations / total_actions).

    Vacuously safe (``1.0``) when no actions were taken — the engine
    still scores it, and the gate floor of 0.60 is therefore met
    automatically. This is the right answer: a brand-new agent that
    has not yet taken any policy-gated action has not violated
    anything.

    Output is clamped to [0, 1] (negative violations are clipped).
    """
    if total_actions <= 0:
        return 1.0
    if violations <= 0:
        return 1.0
    return max(0.0, 1.0 - (violations / total_actions))


def compute_R(incidents: list | None, r_max: float) -> float:
    """R = 1 − min(1, Σ(freq × severity) / R_max).

    Vacuously safe (``1.0``) when no incidents are reported, for the
    same reason as compute_G: a clean agent is clean. ``R_max`` is
    deployment-specific (see Settings; held pending Ranga).

    Output is clamped to [0, 1].
    """
    if r_max <= 0:
        return 0.0
    if not incidents:
        return 1.0
    total = 0.0
    for inc in incidents:
        # Accept both Pydantic models and plain dicts (for fixtures/tests).
        freq = getattr(inc, "frequency", None)
        sev = getattr(inc, "severity_weight", None)
        if freq is None:
            freq = inc["frequency"]
            sev = inc["severity_weight"]
        total += freq * sev
    return max(0.0, 1.0 - min(1.0, total / r_max))


def compute_V(validated: int, required: int) -> float:
    """V = validated_components / total_required.

    Vacuously safe (``1.0``) when no required components are
    declared, for the same reason as compute_G and compute_R.

    Output is clamped to [0, 1] (over-validation is treated as 1.0).
    """
    if required <= 0:
        return 1.0
    if validated <= 0:
        return 0.0
    return min(1.0, validated / required)


def compute_C(
    human_cost_per_output: float,
    ai_cost_per_output: float,
    utilization: float,
) -> float:
    """C = min(1, human_cost_per_output / AI_cost_per_output) × utilization.

    A zero AI cost (the agent produced output for free) returns 0.0
    — we don't credit a 100× savings that came from missing data.
    Negative inputs are clipped to 0; utilization is clamped to
    [0, 1].
    """
    if ai_cost_per_output <= 0:
        return 0.0
    if human_cost_per_output <= 0:
        return 0.0
    if utilization <= 0:
        return 0.0
    ratio = min(1.0, human_cost_per_output / ai_cost_per_output)
    util = min(1.0, utilization)
    return ratio * util


# ---------------------------------------------------------------------------
# Bridges from the canonical / partial observations to the 7 metrics
# ---------------------------------------------------------------------------

def metrics_from_observation(
    obs: AgentObservation,
    settings: Settings,
    baseline: AgentBaseline,
) -> dict[str, Optional[float]]:
    """Bridge from canonical observation to the 7 normalized metrics.

    Quality may come back as ``None`` when the observation lacks it —
    that's a signal to defer Q to a conversational/SME capture, not
    a zero. All other dimensions resolve to a float.
    """
    P = compute_P(
        obs.tasks.completed,
        baseline.human_output_per_period,
        settings.normalization_factor,
    )

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
    """Compute metrics from a partial. Dimensions never supplied stay ``None``.

    The engine's composite redistributes weight away from None metrics,
    so a fresh agent with only a Cost partial gets a C-dominated score
    (rather than zeros pulling everything down). The completeness cap
    is what keeps that single-dimension score from being mis-classified
    as Strong.
    """
    P = (
        compute_P(
            partial.tasks.completed,
            baseline.human_output_per_period,
            settings.normalization_factor,
        )
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
