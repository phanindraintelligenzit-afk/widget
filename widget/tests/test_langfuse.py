"""Tests for the Langfuse source adapter."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from contract import PartialObservation, Executions
from fixtures import load_source
from ingestion.sources import LangfuseAdapter


def test_langfuse_adapter_contract():
    adapter = LangfuseAdapter()
    assert adapter.name == "langfuse"
    
    # Empty payload
    assert adapter.to_partials({}) == []
    
    # Load synthetic fixture
    payload = load_source("langfuse")
    partials = adapter.to_partials(payload)
    assert len(partials) == 2
    
    # Assert details for first agent
    p1 = partials[0]
    assert isinstance(p1, PartialObservation)
    assert p1.agent_id == "agent-multi-001"
    assert p1.source == "langfuse"
    assert p1.executions == Executions(successful=9, attempts=10)
    assert p1.period_start == datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert p1.period_end == datetime(2026, 6, 2, tzinfo=timezone.utc)
    
    # Assert details for second agent
    p2 = partials[1]
    assert p2.agent_id == "agent-perfect-002"
    assert p2.executions == Executions(successful=5, attempts=5)


def test_langfuse_ingest_endpoint(client):
    """Test that posting Langfuse payload to the ingest endpoint works."""
    payload = load_source("langfuse")
    r = client.post("/ingest/source/langfuse", json=payload)
    assert r.status_code == 200, r.text
    ratings = r.json()
    assert len(ratings) == 2
    
    # Verify that the execution dimension was populated
    # The M5 contract calculates E = successful / attempts
    # So agent-multi-001 (successful=9, attempts=10) should have E = 0.90
    # and missing should not contain E
    # Since ingest_partials returns ratings sorted by agent_id:
    # index 0 is agent-multi-001 (successful=9, attempts=10)
    # index 1 is agent-perfect-002 (successful=5, attempts=5)
    rating1 = ratings[0]
    assert rating1["metrics"]["E"] == 0.90
    assert "E" not in rating1["missing"]
    
    rating2 = ratings[1]
    assert rating2["metrics"]["E"] == 1.00
    assert "E" not in rating2["missing"]

