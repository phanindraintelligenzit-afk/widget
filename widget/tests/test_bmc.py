"""Tests for the BMC Remedy adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contract import PartialObservation
from ingestion.sources.bmc import BmcAdapter

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "source_bmc.json"


@pytest.fixture
def bmc_payload():
    return json.loads(_FIXTURE.read_text())


def test_bmc_adapter_reads_synthetic_fixture(bmc_payload):
    """Ensure it maps priority strings to correct severity weights."""
    adapter = BmcAdapter()
    partials = adapter.to_partials(bmc_payload)
    
    assert len(partials) == 2
    
    # 1. chandra-finops has two tickets (Critical and Medium)
    p1 = [p for p in partials if p.agent_id == "chandra-finops"][0]
    assert p1.source == "bmc"
    assert len(p1.incidents) == 2
    
    # Critical -> 1.0
    assert p1.incidents[0].severity_weight == 1.0
    # Medium -> 0.5
    assert p1.incidents[1].severity_weight == 0.5
    
    # 2. agent-perfect-002 has one ticket (Low)
    p2 = [p for p in partials if p.agent_id == "agent-perfect-002"][0]
    assert len(p2.incidents) == 1
    # Low -> 0.3
    assert p2.incidents[0].severity_weight == 0.3


def test_bmc_handles_empty_fields():
    """Missing fields should default gracefully or skip."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "incidents": [
            {
                "agent_id": "empty-agent"
                # Missing priority field, defaults to Medium -> 0.5 weight
            },
            {
                # Missing agent_id field -> gets skipped
                "priority": "Critical"
            },
            {
                "agent_id": "unknown-priority-agent",
                "priority": "SomeWeirdString" # Defaults to 0.5
            }
        ]
    }
    
    adapter = BmcAdapter()
    partials = adapter.to_partials(payload)
    assert len(partials) == 2
    
    p1 = [p for p in partials if p.agent_id == "empty-agent"][0]
    assert len(p1.incidents) == 1
    assert p1.incidents[0].severity_weight == 0.5
    
    p2 = [p for p in partials if p.agent_id == "unknown-priority-agent"][0]
    assert len(p2.incidents) == 1
    assert p2.incidents[0].severity_weight == 0.5
