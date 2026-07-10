"""Tests for the LangGraph adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contract import PartialObservation
from ingestion.sources.langgraph import LangGraphAdapter

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "source_langgraph.json"


@pytest.fixture
def langgraph_payload():
    return json.loads(_FIXTURE.read_text())


def test_langgraph_adapter_reads_synthetic_fixture(langgraph_payload):
    """Ensure it extracts executions and productivity correctly."""
    adapter = LangGraphAdapter()
    partials = adapter.to_partials(langgraph_payload)
    
    assert len(partials) == 2
    
    # 1. chandra-finops
    p1 = [p for p in partials if p.agent_id == "chandra-finops"][0]
    assert p1.source == "langgraph"
    assert p1.executions.successful == 85
    assert p1.executions.attempts == 90
    assert p1.tasks.completed == 85
    
    # 2. agent-perfect-002
    p2 = [p for p in partials if p.agent_id == "agent-perfect-002"][0]
    assert p2.executions.successful == 200
    assert p2.executions.attempts == 200
    assert p2.tasks.completed == 200


def test_langgraph_handles_empty_fields():
    """Missing fields should default to 0 or skip."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "executions": [
            {
                "agent_id": "empty-agent"
                # Missing counts
            },
            {
                # Missing agent_id field -> gets skipped
                "successful_runs": 100
            }
        ]
    }
    
    adapter = LangGraphAdapter()
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    
    p1 = partials[0]
    assert p1.agent_id == "empty-agent"
    assert p1.executions.successful == 0
    assert p1.executions.attempts == 0
    assert p1.tasks.completed == 0
