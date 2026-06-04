"""Coverage / completeness signal — guards the score against a too-narrow
view of an agent.
"""
from __future__ import annotations

import pytest

from contract import DEFAULT_WEIGHTS, Settings
from engine import rate
from engine.gates import NEEDS_OPT_CAP


def _all(value: float) -> dict[str, float]:
    return {k: value for k in DEFAULT_WEIGHTS}


# ---- baseline: with all 7 dimensions, no cap should fire ---------------

def test_full_coverage_unchanged_with_default_floor():
    r = rate(_all(0.85), min_dimensions_for_full_band=5)
    assert r.coverage == 7
    assert sorted(r.dimensions_measured) == sorted(DEFAULT_WEIGHTS.keys())
    assert r.coverage_capped is False
    assert round(r.score) == 85
    assert r.band == "Exceptional"
    assert r.cap_reasons == []


def test_just_at_floor_does_not_cap():
    metrics = {"P": 0.95, "Q": 0.95, "E": 0.95, "G": 0.95, "R": 0.95, "V": None, "C": None}
    r = rate(metrics, min_dimensions_for_full_band=5)
    assert r.coverage == 5
    assert r.coverage_capped is False
    # No cap, but weight redistribution still applies.
    assert r.score > 90


# ---- the cap fires when coverage is below the floor --------------------

def test_below_floor_caps_band_and_records_reason():
    metrics = {"P": None, "Q": 0.95, "E": None, "G": None, "R": None, "V": None, "C": 0.95}
    r = rate(metrics, min_dimensions_for_full_band=5)
    assert r.coverage == 2
    assert sorted(r.dimensions_measured) == ["C", "Q"]
    assert r.coverage_capped is True
    assert r.score == NEEDS_OPT_CAP
    assert r.band == "Needs Optimization"
    assert any("coverage 2/7" in reason for reason in r.cap_reasons)
    # Coverage cap is NOT the same thing as Unsafe — compliance is.
    assert r.unsafe is False
    assert r.gate_failures == []


def test_coverage_disabled_when_setting_is_none():
    metrics = {"C": 0.95}
    metrics.update({k: None for k in "PQEGRV"})
    r = rate(metrics, min_dimensions_for_full_band=None)
    assert r.coverage == 1
    assert r.coverage_capped is False
    # Without the cap, the weight redistribution gives a C-dominated 95.
    assert round(r.score) == 95
    assert r.cap_reasons == []


def test_coverage_cap_compounds_with_compliance_gate():
    """Both caps fire and both reasons are reported. Caps clamp from above,
    so when raw is already below the floor, the score stays where it was —
    both flags still set."""
    metrics = {"P": None, "Q": 0.9, "E": None, "G": 0.1, "R": None, "V": None, "C": 0.9}
    r = rate(metrics, min_dimensions_for_full_band=5)
    assert r.unsafe is True             # compliance gate (G < 0.6)
    assert r.coverage_capped is True    # only 3/7 measured
    assert any(x.startswith("compliance gate") for x in r.cap_reasons)
    assert any(x.startswith("coverage") for x in r.cap_reasons)
    assert r.score <= NEEDS_OPT_CAP


def test_coverage_cap_pulls_high_raw_down():
    """When raw would be Exceptional but only 2 dims are measured, score
    actually moves to NEEDS_OPT_CAP."""
    metrics = {"P": None, "Q": 0.98, "E": None, "G": None, "R": None, "V": None, "C": 0.98}
    r = rate(metrics, min_dimensions_for_full_band=5)
    assert r.coverage_capped is True
    assert r.raw_score > NEEDS_OPT_CAP   # raw was Exceptional
    assert r.score == NEEDS_OPT_CAP       # capped
    assert r.band == "Needs Optimization"


# ---- per-agent baseline: a real partial-coverage agent goes through ---

def test_partial_coverage_agent_through_full_engine(client):
    """End-to-end: aws_cost-only agent gets capped by the default settings."""
    from fixtures import load_source

    client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    r = client.get("/agents/agent-multi-001/score").json()

    assert r["coverage"] == 1
    assert r["dimensions_measured"] == ["C"]
    assert r["coverage_capped"] is True
    assert r["band"] == "Needs Optimization"
    assert r["score"] == NEEDS_OPT_CAP
    assert any("coverage" in reason for reason in r["cap_reasons"])
    assert r["unsafe"] is False  # no compliance gate fired


def test_settings_expose_min_dimensions_for_full_band(client):
    r = client.get("/settings").json()
    assert r["min_dimensions_for_full_band"] == 5

    # Disable the floor → C-only agent recovers its score.
    payload = dict(r)
    payload["min_dimensions_for_full_band"] = 0
    client.put("/settings", json=payload)

    from fixtures import load_source
    client.post("/ingest/source/aws_cost", json=load_source("aws_cost"))
    after = client.get("/agents/agent-multi-001/score").json()
    assert after["coverage_capped"] is False
    assert after["score"] > NEEDS_OPT_CAP
