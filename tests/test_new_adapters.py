"""Tests for PrometheusAdapter, OtelAdapter, and LangfuseAdapter cost/validation extraction."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from contract import PartialObservation, Cost, Validation, Executions
from ingestion.sources import PrometheusAdapter, LangfuseAdapter


def test_prometheus_adapter():
    adapter = PrometheusAdapter()
    assert adapter.name == "prometheus"
    
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "chandra-finops",
                "cost": {
                    "input_tokens": 120000,
                    "output_tokens": 40000,
                    "model_cost": 1.24,
                    "number_of_llm_calls": 5,
                    "Human_cost": 50.0
                },
                "validation": {
                    "required_components": 2,
                    "validated_components": 2,
                    "audit_ready": True
                },
                "executions": {
                    "attempts": 10,
                    "successful": 9
                }
            }
        ]
    }
    
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    p = partials[0]
    
    assert p.agent_id == "chandra-finops"
    assert p.source == "prometheus"
    assert p.cost.model_cost == 1.24
    assert p.cost.input_tokens == 120000
    assert p.cost.output_tokens == 40000
    assert p.validation.required_components == 2
    assert p.validation.validated_components == 2
    assert p.validation.audit_ready is True
    assert p.executions.attempts == 10
    assert p.executions.successful == 9





def test_langfuse_adapter_cost_validation():
    adapter = LangfuseAdapter()
    assert adapter.name == "langfuse"
    
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end": "2026-06-02T00:00:00Z",
        "runs": [
            {
                "agent_id": "chandra-finops",
                "attempts": 10,
                "successful": 9,
                "cost": {
                    "input_tokens": 120000,
                    "output_tokens": 40000,
                    "model_cost": 1.24,
                    "number_of_llm_calls": 5,
                    "Human_cost": 50.0
                },
                "validation": {
                    "required_components": 2,
                    "validated_components": 2,
                    "audit_ready": True
                }
            }
        ]
    }
    
    partials = adapter.to_partials(payload)
    assert len(partials) == 1
    p = partials[0]
    
    assert p.agent_id == "chandra-finops"
    assert p.source == "langfuse"
    assert p.cost.model_cost == 1.24
    assert p.validation.required_components == 2
    assert p.executions.attempts == 10
    assert p.executions.successful == 9
