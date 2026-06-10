"""Tests for the generic Audit Trail adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contract import PartialObservation
from ingestion.sources.audit_trail import AuditTrailAdapter

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "source_audit_trail.json"


@pytest.fixture
def audit_payload():
    return json.loads(_FIXTURE.read_text())


def test_audit_trail_adapter_reads_synthetic_fixture(audit_payload):
    """Ensure it maps violations to the G dimension properly."""
    adapter = AuditTrailAdapter()
    partials = adapter.to_partials(audit_payload)
    
    assert len(partials) == 2
    
    # 1. Agent with violations
    p1 = [p for p in partials if p.agent_id == "chandra-finops"][0]
    assert p1.source == "audit_trail"
    
    assert p1.policy is not None
    assert len(p1.policy.violations) == 2
    assert p1.policy.violations[0].rule == "unauthorized_data_access"
    assert p1.policy.violations[1].rule == "out_of_bounds_action"
    
    # Assert other dimensions remain None
    assert p1.executions is None
    assert p1.incidents is None or len(p1.incidents) == 0

    # 2. Agent with empty violations list
    p2 = [p for p in partials if p.agent_id == "agent-perfect-002"][0]
    assert p2.policy is None


def test_audit_trail_handles_empty_fields():
    """Missing fields shouldn't crash the adapter."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "empty-agent"
            }
        ]
    }
    
    adapter = AuditTrailAdapter()
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    p = partials[0]
    
    assert p.policy is None
