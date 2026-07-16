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


# Legacy tests - disabled because min_dimensions_for_full_band parameter removed
# New completeness tests are in test_completeness.py

@pytest.mark.skip(reason="min_dimensions_for_full_band parameter removed - see test_completeness.py")
def test_full_coverage_unchanged_with_default_floor():
    pass

@pytest.mark.skip(reason="min_dimensions_for_full_band parameter removed - see test_completeness.py")
def test_just_at_floor_does_not_cap():
    pass

@pytest.mark.skip(reason="min_dimensions_for_full_band parameter removed - see test_completeness.py")
def test_below_floor_caps_band_and_records_reason():
    pass

@pytest.mark.skip(reason="min_dimensions_for_full_band parameter removed - see test_completeness.py")
def test_coverage_disabled_when_setting_is_none():
    pass

@pytest.mark.skip(reason="min_dimensions_for_full_band parameter removed - see test_completeness.py")
def test_coverage_cap_compounds_with_compliance_gate():
    pass

@pytest.mark.skip(reason="min_dimensions_for_full_band parameter removed - see test_completeness.py")
def test_coverage_cap_pulls_high_raw_down():
    pass

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

@pytest.mark.skip(reason="min_dimensions_for_full_band setting removed")
def test_settings_expose_min_dimensions_for_full_band():
    pass