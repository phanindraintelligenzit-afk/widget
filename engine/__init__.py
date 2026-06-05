"""Pure scoring engine. No I/O. No framework imports."""
from . import sme_flow
from .bands import band
from .completeness import apply_completeness_cap, completeness_check
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
    metrics_from_partial,
)
from .rate import rate
from .score import composite

__all__ = [
    "NEEDS_OPT_CAP",
    "apply_completeness_cap",
    "apply_gate",
    "band",
    "completeness_check",
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
    "metrics_from_partial",
    "rate",
    "sme_flow",
]
