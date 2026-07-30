"""Coverage / completeness signal — guards the score against a too-narrow
view of an agent.

NOTE: The old coverage system using min_dimensions_for_full_band has been
replaced with a new completeness system. Tests for the new system are in
test_completeness.py.
"""
from __future__ import annotations

import pytest

from contract import DEFAULT_WEIGHTS
from engine import rate


def _all(value: float) -> dict[str, float]:
    return {k: value for k in DEFAULT_WEIGHTS}


# Legacy tests were removed as min_dimensions_for_full_band parameter was removed.
# New completeness tests are in test_completeness.py

# ---- end-to-end through the full API ------------------------------------

def test_partial_coverage_agent_through_full_engine(client):
    """End-to-end: a strictly C-only agent (aws_cost with no
    output_count) gets capped by the completeness system."""
    # ``spend_usd`` with no ``output_count`` → the adapter stays
    # cost-only and the engine has to default the per-output
    # denominator to 1. That puts the agent at 1/7 dimensions.
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [{"agent_id": "agent-multi-001", "spend_usd": 0.30}],
    }
    client.post("/ingest/source/aws_cost", json=payload)
    r = client.get("/agents/agent-multi-001/score").json()
    assert r["coverage"] == 0.143  # 1/7 dimensions
    assert r["capped"] is True      # Completeness cap fires
    pass       # Capped to "Needs Optimization"
    assert r["band"] == "Needs Optimization"
