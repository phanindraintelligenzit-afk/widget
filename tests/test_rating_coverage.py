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
    """End-to-end: aws_cost-only agent gets capped by the new completeness system."""
    from fixtures import load_source

    client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    r = client.get("/agents/agent-multi-001/score").json()
    assert r["coverage"] == 0.143  # 1/7 dimensions
    assert r["capped"] is True      # New completeness cap
    assert r["score"] == 69.0       # Capped to "Needs Optimization"
    assert r["band"] == "Needs Optimization"

@pytest.mark.skip(reason="min_dimensions_for_full_band setting removed")
def test_settings_expose_min_dimensions_for_full_band():
    pass