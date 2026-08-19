"""Compute the 7 normalized [0,1] sub-metrics from an AgentObservation.

Pure functions. No I/O. The only contract dependency is
AgentObservation + Settings + AgentBaseline.

Formulae (per the spec)
-----------------------

::

    P = min(1, AI_output_per_period / human_baseline)              (baseline from settings)
    Q = 0.7·Accuracy + 0.2·Consistency + 0.1·(1 − Hallucination)   (inputs 0–1; null → conversational)
    E = successful_executions / total_attempts
    G = 1 − (total_actions / policy_violations)
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


def compute_G(total_actions: int, policy_violations: int) -> float:
    """G = 1 − (policy_violations / total_actions).

    Official DPI-LS governance formula (per project specification /
    Ranga Sir's documentation): governance strength is measured as one
    minus the ratio of policy violations observed to the number of
    total policy-gated actions. When no violations have been recorded
    the agent is fully compliant → ``1.0``.

    The formula is evaluated exactly as specified and is not clamped to
    [0, 1]: with more actions than violations the ratio exceeds 1 and
    the score goes negative, which surfaces a genuine governance
    failure rather than hiding it behind a floor. The only guard is the
    vacuous case — no violations recorded means nothing to divide by,
    so the agent is compliant.

    Args:
        total_actions:      number of policy-gated actions executed
                            (runtime telemetry, never hardcoded).
        policy_violations:  number of policy violations observed
                            (runtime telemetry, never hardcoded).
    """
    # Official formula: G = 1 - (policy_violations / total_actions)
    if total_actions <= 0:
        return 1.0
    return max(0.0, 1.0 - (policy_violations / total_actions))


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
    model_cost: float,
    completed_outputs: int,
    utilization: float,
    infrastructure_cost: float = 0.0,
) -> float:
    """C = min(1, human_cost_per_output / AI_cost_per_output) × utilization.

    The agent's per-output cost is derived here from the totals the
    caller already has on hand: ``model_cost / completed_outputs``.
    That keeps the contract's ``Cost`` model to just the three numbers
    The dropped fields (``ai_cost_per_output``, ``cloud_cost``,
    ``systems_accessed``) were either a derived value or pure
    observability. Removing them keeps the contract aligned with the
    dashboard: what you see on the card is exactly what the model
    carries.

    Edge cases (in priority order):
    * ``model_cost <= 0 and infrastructure_cost <= 0``         → 1.0 (no spend reported → "free", maximum efficiency).
    * ``completed_outputs <= 0``  → treat as one output (avoids
      div-by-zero AND prevents a single huge ``model_cost`` from
      vanishing into a tiny per-output when the caller didn't supply
      a count).
    * ``human_cost_per_output<=0``→ 0.0 (a human baseline of zero
      means the comparison is meaningless).
    * ``utilization`` is clamped to [0, 1].
    """
    if model_cost <= 0 and infrastructure_cost <= 0:
        return 1.0
    if human_cost_per_output <= 0:
        return 0.0
    outputs = completed_outputs if completed_outputs > 0 else 1
    ai_cost_per_output = (model_cost + infrastructure_cost) / outputs
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
    if obs.productivity:
        h_base = obs.productivity.human_baseline if obs.productivity.human_baseline > 0 else baseline.human_output_per_period
        norm_factor = obs.productivity.normalization_factor if obs.productivity.normalization_factor > 0 else settings.normalization_factor
    else:
        h_base = baseline.human_output_per_period
        norm_factor = settings.normalization_factor

    P = compute_P(
        obs.tasks.completed,
        h_base,
        norm_factor,
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
    # Governance (G)
    # Official formula: G = 1 - (total_actions / policy_violations).
    # total_actions is the number of policy-gated actions executed;
    # policy_violations is the number of violations observed.
    total_actions = obs.policy.total_actions
    policy_violations = len(set(v.when for v in obs.policy.violations if v.rule and v.rule != "none"))
    G = compute_G(total_actions, policy_violations)
    R = compute_R(obs.incidents, settings.r_max)
    V = compute_V(obs.validation.validated_components, obs.validation.required_components)
    # C derives its per-output figure from the cost total divided by
    # the agent's completed output count. The contract's ``Cost``
    # model carries just the three breakdown fields; the
    # per-output math lives here in the engine.
    C = compute_C(
        settings.human_cost_per_output,
        obs.cost.model_cost,
        obs.tasks.completed,
        settings.utilization,
        obs.cost.infrastructure_cost,
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
    if partial.productivity:
        h_base = partial.productivity.human_baseline if partial.productivity.human_baseline > 0 else baseline.human_output_per_period
        norm_factor = partial.productivity.normalization_factor if partial.productivity.normalization_factor > 0 else settings.normalization_factor
    else:
        h_base = baseline.human_output_per_period
        norm_factor = settings.normalization_factor

    P = (
        compute_P(
            partial.tasks.completed,
            h_base,
            norm_factor,
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
        compute_G(
            partial.policy.total_actions,
            len(set(v.when for v in partial.policy.violations)),
        )
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
            partial.cost.model_cost,
            # A Cost-only partial (e.g. AWS Cost Explorer) doesn't
            # carry a tasks block — treat the per-output denominator
            # as 1 in that case, matching the canonical observation
            # path. The completeness cap downstream keeps a single
            # dimension from claiming a Strong band.
            partial.tasks.completed if partial.tasks is not None else 1,
            settings.utilization,
            partial.cost.infrastructure_cost,
        )
        if partial.cost is not None
        else None
    )
    return {"P": P, "Q": Q, "E": E, "G": G, "R": R, "V": V, "C": C}
