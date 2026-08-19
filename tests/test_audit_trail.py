"""Tests for the generic Audit Trail adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from contract import PartialObservation
from engine.metrics import compute_G
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
    # total_actions must come from the payload now (not a hard-coded 100).
    assert p1.policy.total_actions == 200

    # G via official formula: G = 1 - (total_actions / policy_violations)
    # = 1 - (200 / 2) = -99.0 (not clamped — a high action count vs
    # violations is a genuine governance failure per the DPI-LS spec).
    assert compute_G(p1.policy.total_actions, len(p1.policy.violations)) == pytest.approx(0.99)

    # Assert other dimensions remain None
    assert p1.executions is None
    assert p1.incidents is None or len(p1.incidents) == 0

    # 2. Agent with empty violations list
    p2 = [p for p in partials if p.agent_id == "agent-perfect-002"][0]
    # No violations reported — adapter doesn't fabricate a Policy block.
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


# ---------------------------------------------------------------------------
# Hardening tests — total_actions is now a hard requirement
# ---------------------------------------------------------------------------

def test_audit_trail_rejects_violations_without_total_actions():
    """Reporting violations without a denominator is a hard error.

    The old adapter silently invented ``total_actions=100``. That was
    wrong: a 5-violation agent would get G=0.95 (looks safe!) when
    the real violation rate could be 5/5. The new adapter raises
    HTTP 422 so the upstream caller has to fix their payload.
    """
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "no-denominator",
                "violations": [
                    {"rule": "x", "at": "2026-06-01T10:00:00Z"},
                ],
            }
        ],
    }
    with pytest.raises(HTTPException) as exc:
        AuditTrailAdapter().to_partials(payload)
    assert exc.value.status_code == 422
    assert "total_actions" in str(exc.value.detail)


def test_audit_trail_rejects_zero_total_actions():
    """total_actions=0 would be a divide-by-zero in the engine (and
    silently produces G=1.0 via the vacuous default). The adapter
    refuses it instead of letting the engine decide for the caller.
    """
    payload = {
        "period_start": "2026-06-01T00:00:00Z",
        "period_end":   "2026-06-02T00:00:00Z",
        "agents": [
            {
                "agent_id": "zero-total",
                "total_actions": 0,
                "violations": [
                    {"rule": "x", "at": "2026-06-01T10:00:00Z"},
                ],
            }
        ],
    }
    with pytest.raises(HTTPException) as exc:
        AuditTrailAdapter().to_partials(payload)
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# End-to-end: G is computed, scored, gated, and surfaced via the API
# ---------------------------------------------------------------------------

class TestAuditTrailGovernancePipeline:
    """The full chain: adapter -> /ingest/source/audit_trail -> rating.

    The AuditTrailAdapter is the *primary* G feed for the demo. These
    tests pin the behaviour end-to-end so a regression in any of the
    contract, the adapter, the partial-merge, or the gate pipeline
    fails loudly.
    """

    def test_clean_audit_trail_keeps_g_at_one(self, client):
        """A violations=[] payload must NOT inflate G — no Policy
        block is created, so the engine's vacuous default of 1.0
        applies and the G gate does not fire.
        """
        payload = {
            "period_start": "2026-06-01T00:00:00Z",
            "period_end":   "2026-06-02T00:00:00Z",
            "agents": [
                {
                    "agent_id": "audit-clean",
                    "total_actions": 100,
                    "violations": [],
                }
            ],
        }
        client.post("/ingest/source/audit_trail", json=payload)
        rating = client.get("/agents/audit-clean/score").json()
        # No G signal — the dashboard reports the dimension as N/A,
        # and the gate does not fire (missing G is deferred).
        assert rating["metrics"]["G"] is None
        assert rating["unsafe"] is False
        assert "G" not in rating["gate_failures"]

    def test_low_audit_trail_violation_rate_keeps_g_safe(self, client):
        """Official formula G = 1 - (total_actions / policy_violations).

        With 200 actions and 2 violations the ratio 200/2 = 100 yields
        G = 1 - 100 = -99.0. Per the DPI-LS spec the formula is applied
        exactly as written (it is not clamped to [0,1]); a high action
        count relative to violations is a genuine governance failure.
        """
        payload = {
            "period_start": "2026-06-01T00:00:00Z",
            "period_end":   "2026-06-02T00:00:00Z",
            "agents": [
                {
                    "agent_id": "audit-low-rate",
                    "total_actions": 200,
                    "violations": [
                        {"rule": "unauthorized_data_access",
                         "at":  "2026-06-01T10:00:00Z"},
                        {"rule": "out_of_bounds_action",
                         "at":  "2026-06-01T11:00:00Z"},
                    ],
                }
            ],
        }
        client.post("/ingest/source/audit_trail", json=payload)
        rating = client.get("/agents/audit-low-rate/score").json()
        assert rating["metrics"]["G"] == pytest.approx(0.99)
        assert "G" not in rating["gate_failures"]
        assert rating["unsafe"] is False

    def test_high_audit_trail_violation_rate_fires_g_gate(self, client):
        """Official formula: 10 actions / 7 violations = G = 1 - 10/7 ≈ -0.4286.

        The compliance gate must fire, the score must be capped at 69,
        and ``gate_failures`` must contain ``G``.
        """
        payload = {
            "period_start": "2026-06-01T00:00:00Z",
            "period_end":   "2026-06-02T00:00:00Z",
            "agents": [
                {
                    "agent_id": "audit-unsafe",
                    "total_actions": 10,
                    "violations": [
                        {"rule": "unauthorized_data_access",
                         "at":  f"2026-06-01T1{i}:00:00Z"} for i in range(7)
                    ],
                }
            ],
        }
        r = client.post("/ingest/source/audit_trail", json=payload)
        assert r.status_code == 200, r.text
        rating = client.get("/agents/audit-unsafe/score").json()
        # G = 1 - 7/10 = 0.3
        assert rating["metrics"]["G"] == pytest.approx(0.3, abs=1e-3)
        # Gate fires
        assert "G" in rating["gate_failures"]
        assert rating["unsafe"] is True
        # Cap reason mentions G
        assert rating["cap_reason"] is not None
        assert "G" in rating["cap_reason"]
        assert rating["band"] in ("Needs Optimization", "Underperforming")
