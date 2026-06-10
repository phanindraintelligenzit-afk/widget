"""Tests for the Ray observability adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from contract import PartialObservation
from engine.metrics import compute_G
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

    # Policy — total_actions is now derived from Ray's own counters
    # (successful_tasks + task_retries + actor_crashes = 100+5+1=106),
    # not a hard-coded 100.
    assert p1.policy is not None
    assert len(p1.policy.violations) == 2
    assert p1.policy.violations[0].rule == "quota.memory.oom"
    assert p1.policy.violations[1].rule == "quota.api.rate_limit"
    assert p1.policy.total_actions == 106
    # G is 2/106 = 0.0189 violation rate → G = 0.9811
    assert compute_G(len(p1.policy.violations), p1.policy.total_actions) == pytest.approx(0.9811, abs=1e-3)

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


# ---------------------------------------------------------------------------
# Hardening tests — total_actions derivation and explicit override
# ---------------------------------------------------------------------------

def test_ray_derives_total_actions_from_own_counters():
    """When the payload doesn't include ``total_actions``, the
    adapter sums ``successful_tasks + task_retries + actor_crashes``
    to get the G denominator. Pins the derivation so it doesn't
    silently regress to the old hard-coded 100.
    """
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "ray-derive",
                "successful_tasks": 50,
                "task_retries":      5,
                "actor_crashes":     2,
                "quota_breaches": [
                    {"resource": "memory.oom", "at": "2026-06-01T10:00:00Z"},
                ],
            }
        ],
    }
    p = RayAdapter().to_partials(payload)[0]
    assert p.policy.total_actions == 57  # 50 + 5 + 2
    assert compute_G(len(p.policy.violations), p.policy.total_actions) == pytest.approx(1 - 1/57)


def test_ray_explicit_total_actions_overrides_derivation():
    """An explicit ``total_actions`` field in the payload wins over
    the derived value. This is the escape hatch for callers who
    measure G against a different denominator (e.g. total policy
    evaluations, not just Ray's own internal counters).
    """
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "ray-explicit",
                "successful_tasks": 50,
                "task_retries":      5,
                "actor_crashes":     2,
                "total_actions":     1000,  # explicit — overrides 57
                "quota_breaches": [
                    {"resource": "memory.oom", "at": "2026-06-01T10:00:00Z"},
                ],
            }
        ],
    }
    p = RayAdapter().to_partials(payload)[0]
    assert p.policy.total_actions == 1000


def test_ray_rejects_breaches_with_zero_derived_total():
    """If the payload has quota_breaches but neither ``total_actions``
    nor the derived counters add up to anything positive, the
    adapter raises 422. A 0 denominator would silently inflate G
    to 1.0 via the engine's vacuous default — the worst possible
    miss on the governance dimension.
    """
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "ray-no-counter",
                # No successful_tasks / task_retries / actor_crashes —
                # derived total is 0. Adapter must NOT invent a value.
                "quota_breaches": [
                    {"resource": "memory.oom", "at": "2026-06-01T10:00:00Z"},
                ],
            }
        ],
    }
    with pytest.raises(HTTPException) as exc:
        RayAdapter().to_partials(payload)
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# End-to-end: G from Ray flows through the API and fires the gate
# ---------------------------------------------------------------------------

class TestRayGovernancePipeline:

    def test_clean_ray_keeps_g_at_one(self, client):
        """No breaches, no G signal — gate is deferred."""
        payload = {
            "period_start": "2026-06-01T00:00:00Z",
            "period_end":   "2026-06-02T00:00:00Z",
            "agents": [
                {
                    "agent_id": "ray-clean",
                    "successful_tasks": 100,
                    "task_retries":      2,
                    "actor_crashes":     0,
                }
            ],
        }
        client.post("/ingest/source/ray", json=payload)
        rating = client.get("/agents/ray-clean/score").json()
        assert rating["metrics"]["G"] is None
        assert rating["unsafe"] is False
        assert "G" not in rating["gate_failures"]

    def test_ray_quota_breach_density_fires_g_gate(self, client):
        """7 quota_breaches out of 10 actions ⇒ G=0.30, gate fires."""
        payload = {
            "period_start": "2026-06-01T00:00:00Z",
            "period_end":   "2026-06-02T00:00:00Z",
            "agents": [
                {
                    "agent_id": "ray-unsafe",
                    "total_actions": 10,
                    "quota_breaches": [
                        {"resource": f"quota.{i}",
                         "at":         f"2026-06-01T1{i}:00:00Z"}
                        for i in range(7)
                    ],
                }
            ],
        }
        r = client.post("/ingest/source/ray", json=payload)
        assert r.status_code == 200, r.text
        rating = client.get("/agents/ray-unsafe/score").json()
        assert rating["metrics"]["G"] == pytest.approx(0.30)
        assert "G" in rating["gate_failures"]
        assert rating["unsafe"] is True
        assert rating["score"] <= 69
