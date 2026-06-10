"""Tests for the ServiceNow adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contract import PartialObservation
from ingestion.sources.servicenow import ServiceNowAdapter

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "source_servicenow.json"


@pytest.fixture
def servicenow_payload():
    return json.loads(_FIXTURE.read_text())


def test_servicenow_adapter_reads_synthetic_fixture(servicenow_payload):
    """Ensure it maps impact values to correct severity weights."""
    adapter = ServiceNowAdapter()
    partials = adapter.to_partials(servicenow_payload)
    
    assert len(partials) == 2
    
    # 1. agent-multi-001 has two tickets (impact 2 and impact 3)
    p1 = [p for p in partials if p.agent_id == "agent-multi-001"][0]
    assert p1.source == "servicenow"
    assert len(p1.incidents) == 2
    
    # Impact 2 -> 0.6
    assert p1.incidents[0].severity_weight == 0.6
    # Impact 3 -> 0.3
    assert p1.incidents[1].severity_weight == 0.3
    
    # 2. another-agent has one ticket (impact 1)
    p2 = [p for p in partials if p.agent_id == "another-agent"][0]
    assert len(p2.incidents) == 1
    # Impact 1 -> 1.0
    assert p2.incidents[0].severity_weight == 1.0


def test_servicenow_handles_empty_fields():
    """Missing fields should default gracefully or skip."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "tickets": [
            {
                "u_agent_id": "empty-agent"
                # Missing impact field, defaults to 3 -> 0.3 weight
            },
            {
                # Missing u_agent_id field -> gets skipped
                "impact": 1
            }
        ]
    }
    
    adapter = ServiceNowAdapter()
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    p = partials[0]
    
    assert p.agent_id == "empty-agent"
    assert len(p.incidents) == 1
    assert p.incidents[0].severity_weight == 0.3
