"""Tunables. All weights, gates, and baselines live here — never in code."""
from __future__ import annotations

from pydantic import BaseModel, Field


# Composite weights — must sum to 1.0. Hardcoded reference values from the spec.
DEFAULT_WEIGHTS: dict[str, float] = {
    "P": 0.15,
    "Q": 0.20,
    "E": 0.15,
    "G": 0.20,
    "R": 0.15,
    "V": 0.10,
    "C": 0.05,
}

DEFAULT_Q_SUB_WEIGHTS: dict[str, float] = {
    "accuracy": 0.70,
    "consistency": 0.20,
    "hallucination": 0.10,
}

# Provisional default pending Ranga sign-off:
# R_max (risk threshold) is set at 0.30 (meaning we hard-gate when safety score R < 0.70)
# with a soft interrupt band of 0.20-0.30.
DEFAULT_GATE_THRESHOLDS: dict[str, float] = {"G": 0.60, "R": 0.50, "V": 0.60}


class Settings(BaseModel):
    """Per-deployment tunables. Per-agent baselines live in AgentBaseline."""
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    q_sub_weights: dict[str, float]
    gate_thresholds: dict[str, float]
    r_max: float
    human_cost_per_output: float = 50.0
    utilization: float = 1.0
    normalization_factor: float = 1.0
    input_token_price: float = 0.000005
    output_token_price: float = 0.000015
    ground_truth_dataset_path: str | None = None

    # Coverage cap. The composite redistributes weight off None metrics, so an
    # agent with only 1–2 dimensions reported could otherwise score 100. This
    # threshold caps the band at "Needs Optimization" when coverage is below
    # the floor, with the reason surfaced on the Rating.
    min_dimensions_for_full_band: int = 4


class AgentBaseline(BaseModel):
    """Per-agent productivity baseline used for P."""
    agent_id: str
    human_output_per_period: float
