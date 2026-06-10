"""Tests for the Ray observability adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contract import PartialObservation
from ingestion.sources.ray import RayAdapter

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "source_ray.json"


@pytest.fixture
def ray_payload():
    return json.loads(_FIXTURE.read_text())


def test_ray_adapter_reads_synthetic_fixture(ray_payload):
    """Ensure it processes the synthetic fixture properly."""
    adapter = RayAdapter()
    partials = adapter.to_partials(ray_payload)
    
    assert len(partials) == 2
    
    # 1. First agent has retries, crashes, and quota breaches
    p1 = [p for p in partials if p.agent_id == "agent-multi-001"][0]
    assert p1.source == "ray"
    
    # Executions
    assert p1.executions is not None
    assert p1.executions.successful == 100
    assert p1.executions.attempts == 105  # 100 successful + 5 retries
    
    # Incidents
    assert len(p1.incidents) == 1
    assert p1.incidents[0].severity_weight == 0.8
    assert p1.incidents[0].source == "ray.actor_crash"
    
    # Policy
    assert p1.policy is not None
    assert len(p1.policy.violations) == 2
    assert p1.policy.violations[0].rule == "quota.memory.oom"
    assert p1.policy.violations[1].rule == "quota.api.rate_limit"

    # 2. Second agent is perfect
    p2 = [p for p in partials if p.agent_id == "agent-perfect-002"][0]
    assert p2.executions is not None
    assert p2.executions.successful == 50
    assert p2.executions.attempts == 50
    
    assert len(p2.incidents) == 0
    assert p2.policy is None


def test_ray_adapter_handles_empty_fields():
    """Missing metrics shouldn't crash the adapter, and should map to None."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "empty-agent"
            }
        ]
    }
    
    adapter = RayAdapter()
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    p = partials[0]
    
    assert p.executions is None
    assert len(p.incidents) == 0
    assert p.policy is None
