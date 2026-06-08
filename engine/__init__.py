"""Pure scoring engine. No I/O. No framework imports.

The engine exposes the public functions an API or test calls:

* :func:`composite`           — weighted geometric mean × 100
* :func:`gate_check` / :func:`apply_gate` — compliance floors on G/R/V
* :func:`completeness_check` / :func:`apply_completeness_cap` — coverage policy
* :func:`rate`                — top-level: wires the three together into a ``Rating``
* :func:`band`                — score → band name
* :func:`compute_*`           — the 7 individual metric formulae
* :func:`metrics_from_observation` / :func:`metrics_from_partial` — bridges

The engine core (everything in this package *except* :mod:`sme_flow`)
is framework-free. :mod:`sme_flow` is the LangGraph-backed M6
conversational state machine and is allowed to depend on langgraph
per the project spec.
"""
from . import sme_flow
from .bands import (
    EXCEPTIONAL,
    NEEDS_OPTIMIZATION,
    NEEDS_OPT_CAP,
    STRONG,
    UNDERPERFORMING,
    band,
)
from .completeness import (
    DEFAULT_MIN_DIMENSIONS,
    GATED,
    apply_completeness_cap,
    completeness_check,
)
from .gates import (
    GATED_METRICS,
    NEEDS_OPT_CAP as _GATES_CAP,  # re-exported below as the canonical
    apply_gate,
    gate_check,
)
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

# Surface the single source of truth for the band cap. The two
# modules used to define it independently; now both point at the
# same constant in :mod:`engine.bands`. We re-export it from
# :mod:`engine.gates` as ``NEEDS_OPT_CAP`` for back-compat.
NEEDS_OPT_CAP = NEEDS_OPT_CAP

__all__ = [
    "DEFAULT_MIN_DIMENSIONS",
    "EXCEPTIONAL",
    "GATED",
    "GATED_METRICS",
    "NEEDS_OPTIMIZATION",
    "NEEDS_OPT_CAP",
    "STRONG",
    "UNDERPERFORMING",
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
