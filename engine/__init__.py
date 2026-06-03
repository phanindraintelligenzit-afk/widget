"""Pure scoring engine. No I/O. No framework imports."""
from .bands import band
from .gates import NEEDS_OPT_CAP, apply_gate, gate_check
from .metrics import (
    compute_C,
    compute_E,
    compute_G,
    compute_P,
    compute_Q,
    compute_R,
    compute_V,
    metrics_from_observation,
)
from .rate import rate
from .score import composite

__all__ = [
    "NEEDS_OPT_CAP",
    "apply_gate",
    "band",
    "composite",
    "compute_C",
    "compute_E",
    "compute_G",
    "compute_P",
    "compute_Q",
    "compute_R",
    "compute_V",
    "gate_check",
    "metrics_from_observation",
    "rate",
]
