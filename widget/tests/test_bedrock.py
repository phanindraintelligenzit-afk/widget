"""Tests for the AWS Bedrock adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contract import PartialObservation
from ingestion.sources.bedrock import BedrockAdapter

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "source_bedrock.json"


@pytest.fixture
def bedrock_payload():
    return json.loads(_FIXTURE.read_text())


def test_bedrock_adapter_reads_synthetic_fixture(bedrock_payload):
    """Ensure it extracts token and cost usage correctly."""
    adapter = BedrockAdapter()
    partials = adapter.to_partials(bedrock_payload)
    
    assert len(partials) == 2
    
    # 1. chandra-finops
    p1 = [p for p in partials if p.agent_id == "chandra-finops"][0]
    assert p1.source == "bedrock"
    assert p1.cost is not None
    assert p1.cost.input_tokens == 15000
    assert p1.cost.output_tokens == 4000
    assert p1.cost.model_cost == 0.06
    
    # 2. agent-perfect-002
    p2 = [p for p in partials if p.agent_id == "agent-perfect-002"][0]
    assert p2.cost is not None
    assert p2.cost.input_tokens == 2000
    assert p2.cost.output_tokens == 500
    assert p2.cost.model_cost == 0.01


def test_bedrock_handles_empty_fields():
    """Missing fields should default to 0."""
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "bedrock_usage": [
            {
                "agent_id": "empty-agent"
                # Missing tokens and cost
            },
            {
                # Missing agent_id field -> gets skipped
                "input_tokens": 1000
            }
        ]
    }
    
    adapter = BedrockAdapter()
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    
    p1 = [p for p in partials if p.agent_id == "empty-agent"][0]
    assert p1.cost.input_tokens == 0
    assert p1.cost.output_tokens == 0
    assert p1.cost.model_cost == 0.0
