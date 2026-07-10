"""Tests for the SAP HR adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contract import PartialObservation
from ingestion.sources.sap_hr import SapHrAdapter

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "source_sap_hr.json"


@pytest.fixture
def sap_hr_payload():
    return json.loads(_FIXTURE.read_text())


def test_sap_hr_adapter_reads_synthetic_fixture(sap_hr_payload):
    """Ensure it extracts policy violations correctly."""
    adapter = SapHrAdapter()
    partials = adapter.to_partials(sap_hr_payload)
    
    assert len(partials) == 2
    
    # 1. chandra-finops
    p1 = [p for p in partials if p.agent_id == "chandra-finops"][0]
    assert p1.source == "sap_hr"
    assert p1.policy is not None
    assert p1.policy.total_actions == 50
    assert len(p1.policy.violations) == 1
    assert p1.policy.violations[0].rule == "unauthorized_employee_record_access"
    
    # 2. agent-perfect-002
    p2 = [p for p in partials if p.agent_id == "agent-perfect-002"][0]
    assert p2.policy.total_actions == 120
    assert len(p2.policy.violations) == 0


def test_sap_hr_handles_empty_fields():
    """Missing fields should default to 0 or skip."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "hr_alerts": [
            {
                "agent_id": "empty-agent"
                # Missing total_actions and violations
            },
            {
                # Missing agent_id field -> gets skipped
                "total_scanned_actions": 100
            }
        ]
    }
    
    adapter = SapHrAdapter()
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    
    p1 = partials[0]
    assert p1.agent_id == "empty-agent"
    assert p1.policy.total_actions == 0
    assert len(p1.policy.violations) == 0
