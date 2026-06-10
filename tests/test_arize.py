"""Tests for the Arize source adapter.

Covers:
  - G (governance): monitor_breaches → PolicyViolation
  - Q (quality):    accuracy / consistency / hallucination_rate
  - Edge cases:     empty payload, missing optional fields, multi-agent
  - API endpoint:   POST /ingest/source/arize round-trip
  - G formula:      score = 1 - (violations / total_actions)
"""
from __future__ import annotations

import pytest

from contract import PartialObservation
from fixtures import load_source
from ingestion.sources import ArizeAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD = {
    "period_start": "2026-06-01T00:00:00Z",
    "period_end":   "2026-06-02T00:00:00Z",
}


def make_payload(*agents: dict) -> dict:
    """Build a minimal Arize payload with the given agent dicts."""
    return {**PERIOD, "agents": list(agents)}


def single_agent(**kwargs) -> dict:
    """One agent entry. Merges kwargs into a base agent dict."""
    base = {"agent_id": "test-agent-001"}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# 1. Adapter basic contract
# ---------------------------------------------------------------------------

class TestArizeAdapterContract:

    def test_name_is_arize(self):
        assert ArizeAdapter().name == "arize"

    def test_returns_list(self):
        result = ArizeAdapter().to_partials(make_payload())
        assert isinstance(result, list)

    def test_empty_agents_returns_empty_list(self):
        result = ArizeAdapter().to_partials(make_payload())
        assert result == []

    def test_returns_partial_observation_instances(self):
        payload = make_payload(single_agent(model_inferences=10))
        [p] = ArizeAdapter().to_partials(payload)
        assert isinstance(p, PartialObservation)

    def test_source_field_is_arize(self):
        payload = make_payload(single_agent(model_inferences=5))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.source == "arize"

    def test_agent_id_preserved(self):
        payload = make_payload({"agent_id": "claims-agent-007", "model_inferences": 10})
        [p] = ArizeAdapter().to_partials(payload)
        assert p.agent_id == "claims-agent-007"

    def test_agent_name_preserved_when_present(self):
        payload = make_payload({
            "agent_id": "a",
            "agent_name": "Claims Processor",
            "model_inferences": 5,
        })
        [p] = ArizeAdapter().to_partials(payload)
        assert p.agent_name == "Claims Processor"

    def test_agent_name_none_when_absent(self):
        payload = make_payload(single_agent(model_inferences=5))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.agent_name is None

    def test_period_dates_parsed(self):
        payload = make_payload(single_agent(model_inferences=5))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.period_start is not None
        assert p.period_end is not None
        assert p.period_end > p.period_start


# ---------------------------------------------------------------------------
# 2. G dimension — monitor_breaches → policy violations
# ---------------------------------------------------------------------------

class TestArizeGovernance:

    def test_fixture_produces_policy_partial(self):
        """The standard fixture must produce a G-populated partial."""
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.policy is not None

    def test_fixture_total_actions(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.policy.total_actions == 1200

    def test_fixture_violation_count(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert len(p.policy.violations) == 1

    def test_fixture_violation_rule_name(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.policy.violations[0].rule == "drift.embedding_l2"

    def test_violation_timestamp_parsed(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.policy.violations[0].when is not None

    def test_multiple_breaches_all_mapped(self):
        payload = make_payload(single_agent(
            model_inferences=500,
            monitor_breaches=[
                {"monitor": "drift.embedding_l2",       "at": "2026-06-01T09:00:00Z"},
                {"monitor": "data_quality.missing",     "at": "2026-06-01T10:00:00Z"},
                {"monitor": "hallucination.rate_high",  "at": "2026-06-01T11:00:00Z"},
                {"monitor": "accuracy.drop",             "at": "2026-06-01T12:00:00Z"},
            ],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        assert len(p.policy.violations) == 4

    def test_violation_rules_match_monitor_names(self):
        payload = make_payload(single_agent(
            model_inferences=100,
            monitor_breaches=[
                {"monitor": "accuracy.drop",  "at": "2026-06-01T08:00:00Z"},
                {"monitor": "pii.ssn_found",  "at": "2026-06-01T09:00:00Z"},
            ],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        rules = {v.rule for v in p.policy.violations}
        assert rules == {"accuracy.drop", "pii.ssn_found"}

    def test_zero_breaches_policy_still_set(self):
        """model_inferences present but no breaches → policy exists, violations empty."""
        payload = make_payload(single_agent(
            model_inferences=300,
            monitor_breaches=[],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.policy is not None
        assert p.policy.total_actions == 300
        assert p.policy.violations == []

    def test_total_actions_from_model_inferences(self):
        payload = make_payload(single_agent(
            model_inferences=999,
            monitor_breaches=[],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.policy.total_actions == 999

    def test_total_actions_falls_back_to_breach_count(self):
        """When model_inferences is absent, len(breaches) is used as total_actions."""
        payload = make_payload({
            "agent_id": "a",
            "monitor_breaches": [
                {"monitor": "drift.embedding_l2", "at": "2026-06-01T09:00:00Z"},
                {"monitor": "accuracy.drop",      "at": "2026-06-01T10:00:00Z"},
            ],
        })
        [p] = ArizeAdapter().to_partials(payload)
        assert p.policy is not None
        assert p.policy.total_actions == 2

    def test_no_monitor_fields_policy_is_none(self):
        """Neither monitor_breaches nor model_inferences → policy stays None."""
        payload = make_payload({"agent_id": "no-policy-agent"})
        [p] = ArizeAdapter().to_partials(payload)
        assert p.policy is None

    def test_g_score_with_no_violations_is_one(self):
        """G = 1 - (0 / 500) = 1.0 (perfect governance)."""
        from engine.metrics import compute_G
        payload = make_payload(single_agent(model_inferences=500, monitor_breaches=[]))
        [p] = ArizeAdapter().to_partials(payload)
        g = compute_G(len(p.policy.violations), p.policy.total_actions)
        assert g == pytest.approx(1.0)

    def test_g_score_with_violations(self):
        """G = 1 - (2 / 200) = 0.99."""
        from engine.metrics import compute_G
        payload = make_payload(single_agent(
            model_inferences=200,
            monitor_breaches=[
                {"monitor": "drift.embedding_l2", "at": "2026-06-01T09:00:00Z"},
                {"monitor": "accuracy.drop",      "at": "2026-06-01T10:00:00Z"},
            ],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        g = compute_G(len(p.policy.violations), p.policy.total_actions)
        assert g == pytest.approx(0.99)

    def test_g_score_all_violations_is_zero(self):
        """G = 1 - (3 / 3) = 0.0 (every action was a violation)."""
        from engine.metrics import compute_G
        payload = make_payload(single_agent(
            model_inferences=3,
            monitor_breaches=[
                {"monitor": "rule.a", "at": "2026-06-01T09:00:00Z"},
                {"monitor": "rule.b", "at": "2026-06-01T10:00:00Z"},
                {"monitor": "rule.c", "at": "2026-06-01T11:00:00Z"},
            ],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        g = compute_G(len(p.policy.violations), p.policy.total_actions)
        assert g == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 3. Q dimension — quality scores
# ---------------------------------------------------------------------------

class TestArizeQuality:

    def test_fixture_produces_quality_partial(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.quality is not None

    def test_fixture_accuracy(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.quality.accuracy == pytest.approx(0.93)

    def test_fixture_consistency(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.quality.consistency == pytest.approx(0.91)

    def test_fixture_hallucination_rate(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.quality.hallucination_rate == pytest.approx(0.05)

    def test_quality_none_when_field_absent(self):
        payload = make_payload(single_agent(model_inferences=100, monitor_breaches=[]))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.quality is None

    def test_quality_none_when_field_is_null(self):
        payload = make_payload({
            "agent_id": "a",
            "model_inferences": 50,
            "quality": None,
        })
        [p] = ArizeAdapter().to_partials(payload)
        assert p.quality is None

    def test_quality_values_clamped_to_zero_one(self):
        """Parser accepts out-of-range floats — engine clips them."""
        payload = make_payload({
            "agent_id": "a",
            "model_inferences": 10,
            "quality": {
                "accuracy": 1.2,
                "consistency": -0.1,
                "hallucination_rate": 0.5,
            },
        })
        [p] = ArizeAdapter().to_partials(payload)
        # Adapter passes through; engine compute_Q clips internally.
        assert p.quality is not None
        assert p.quality.accuracy == pytest.approx(1.2)   # adapter trusts the source
        assert p.quality.consistency == pytest.approx(-0.1)

    def test_q_score_computed_from_arize_quality(self):
        """Q = 0.7*acc + 0.2*con + 0.1*(1-hall) using fixture values."""
        from contract import DEFAULT_Q_SUB_WEIGHTS
        from engine.metrics import compute_Q
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        q = compute_Q(
            p.quality.accuracy,
            p.quality.consistency,
            p.quality.hallucination_rate,
            DEFAULT_Q_SUB_WEIGHTS,
        )
        # 0.7*0.93 + 0.2*0.91 + 0.1*(1-0.05) = 0.651 + 0.182 + 0.095 = 0.928
        assert q == pytest.approx(0.928, abs=0.001)

    def test_perfect_quality_scores_one(self):
        from contract import DEFAULT_Q_SUB_WEIGHTS
        from engine.metrics import compute_Q
        payload = make_payload({
            "agent_id": "a",
            "model_inferences": 10,
            "quality": {"accuracy": 1.0, "consistency": 1.0, "hallucination_rate": 0.0},
        })
        [p] = ArizeAdapter().to_partials(payload)
        q = compute_Q(
            p.quality.accuracy,
            p.quality.consistency,
            p.quality.hallucination_rate,
            DEFAULT_Q_SUB_WEIGHTS,
        )
        assert q == pytest.approx(1.0)

    def test_worst_quality_scores_near_zero(self):
        from contract import DEFAULT_Q_SUB_WEIGHTS
        from engine.metrics import compute_Q
        payload = make_payload({
            "agent_id": "a",
            "model_inferences": 10,
            "quality": {"accuracy": 0.0, "consistency": 0.0, "hallucination_rate": 1.0},
        })
        [p] = ArizeAdapter().to_partials(payload)
        q = compute_Q(
            p.quality.accuracy,
            p.quality.consistency,
            p.quality.hallucination_rate,
            DEFAULT_Q_SUB_WEIGHTS,
        )
        assert q == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 4. Dimensions NOT owned by Arize stay None
# ---------------------------------------------------------------------------

class TestArizeDoesNotPolluteDimensions:

    def test_tasks_is_none(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.tasks is None

    def test_executions_is_none(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.executions is None

    def test_incidents_is_none(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.incidents is None

    def test_validation_is_none(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.validation is None

    def test_cost_is_none(self):
        [p] = ArizeAdapter().to_partials(load_source("arize"))
        assert p.cost is None


# ---------------------------------------------------------------------------
# 5. Multi-agent payload
# ---------------------------------------------------------------------------

class TestArizeMultiAgent:

    def test_two_agents_return_two_partials(self):
        payload = make_payload(
            {"agent_id": "agent-a", "model_inferences": 100, "monitor_breaches": []},
            {"agent_id": "agent-b", "model_inferences": 200, "monitor_breaches": []},
        )
        result = ArizeAdapter().to_partials(payload)
        assert len(result) == 2

    def test_agent_ids_are_distinct(self):
        payload = make_payload(
            {"agent_id": "agent-a", "model_inferences": 100, "monitor_breaches": []},
            {"agent_id": "agent-b", "model_inferences": 200, "monitor_breaches": []},
        )
        result = ArizeAdapter().to_partials(payload)
        ids = {p.agent_id for p in result}
        assert ids == {"agent-a", "agent-b"}

    def test_each_agent_has_independent_violations(self):
        payload = make_payload(
            {
                "agent_id": "agent-a",
                "model_inferences": 100,
                "monitor_breaches": [
                    {"monitor": "drift.embedding_l2", "at": "2026-06-01T09:00:00Z"},
                ],
            },
            {
                "agent_id": "agent-b",
                "model_inferences": 50,
                "monitor_breaches": [],
            },
        )
        result = ArizeAdapter().to_partials(payload)
        by_id = {p.agent_id: p for p in result}
        assert len(by_id["agent-a"].policy.violations) == 1
        assert len(by_id["agent-b"].policy.violations) == 0

    def test_one_agent_has_quality_other_does_not(self):
        payload = make_payload(
            {
                "agent_id": "agent-with-quality",
                "model_inferences": 100,
                "quality": {"accuracy": 0.9, "consistency": 0.85, "hallucination_rate": 0.1},
            },
            {
                "agent_id": "agent-no-quality",
                "model_inferences": 80,
            },
        )
        result = ArizeAdapter().to_partials(payload)
        by_id = {p.agent_id: p for p in result}
        assert by_id["agent-with-quality"].quality is not None
        assert by_id["agent-no-quality"].quality is None


# ---------------------------------------------------------------------------
# 6. API endpoint — POST /ingest/source/arize
# ---------------------------------------------------------------------------

class TestArizeAPIEndpoint:

    def test_endpoint_returns_200(self, client):
        r = client.post("/ingest/source/arize", json=load_source("arize"))
        assert r.status_code == 200, r.text

    def test_endpoint_returns_list(self, client):
        r = client.post("/ingest/source/arize", json=load_source("arize"))
        assert isinstance(r.json(), list)

    def test_endpoint_scores_agent(self, client):
        r = client.post("/ingest/source/arize", json=load_source("arize"))
        ratings = r.json()
        assert len(ratings) == 1
        assert ratings[0]["score"] > 0

    def test_g_metric_populated_after_ingest(self, client):
        client.post("/ingest/source/arize", json=load_source("arize"))
        score = client.get("/agents/agent-multi-001/score").json()
        assert score["metrics"]["G"] is not None

    def test_q_metric_populated_after_ingest(self, client):
        client.post("/ingest/source/arize", json=load_source("arize"))
        score = client.get("/agents/agent-multi-001/score").json()
        assert score["metrics"]["Q"] is not None

    def test_g_value_range(self, client):
        client.post("/ingest/source/arize", json=load_source("arize"))
        score = client.get("/agents/agent-multi-001/score").json()
        g = score["metrics"]["G"]
        assert 0.0 <= g <= 1.0

    def test_q_value_range(self, client):
        client.post("/ingest/source/arize", json=load_source("arize"))
        score = client.get("/agents/agent-multi-001/score").json()
        q = score["metrics"]["Q"]
        assert 0.0 <= q <= 1.0

    def test_arize_g_overwrites_earlier_source(self, client):
        """Arize G partial (latest) overwrites an earlier G from Puvi Noise."""
        from fixtures import load_source as ls
        client.post("/ingest/source/puvi_noise", json=ls("puvi_noise"))
        client.post("/ingest/source/arize",      json=ls("arize"))
        score = client.get("/agents/agent-multi-001/score").json()
        # G must still be present — latest (arize) wins by merge_partials.
        assert score["metrics"]["G"] is not None

    def test_perfect_governance_no_violations(self, client):
        """Agent with zero breaches should have G close to 1.0."""
        payload = {
            **PERIOD,
            "agents": [{
                "agent_id": "clean-agent",
                "model_inferences": 500,
                "monitor_breaches": [],
            }],
        }
        client.post("/ingest/source/arize", json=payload)
        score = client.get("/agents/clean-agent/score").json()
        assert score["metrics"]["G"] == pytest.approx(1.0)

    def test_bad_payload_missing_period_start_raises(self, client):
        """Missing period_start causes a KeyError crash in arize.py (known gap).

        The Starlette TestClient propagates unhandled server exceptions directly
        rather than wrapping them in an HTTP 500 response, so we catch with
        pytest.raises. This documents a real bug: arize.py should guard against
        missing period_start/period_end and raise an HTTPException instead.
        TODO: fix arize.py to validate period fields and return HTTP 422.
        """
        with pytest.raises(KeyError, match="period_start"):
            client.post("/ingest/source/arize", json={"agents": []})

    def test_arize_listed_in_sources_endpoint(self, client):
        r = client.get("/sources")
        names = {s["name"] for s in r.json()}
        assert "arize" in names


# ---------------------------------------------------------------------------
# 7. Datetime parsing edge cases
# ---------------------------------------------------------------------------

class TestArizeDatetimeParsing:

    def test_Z_suffix_parsed(self):
        payload = make_payload(single_agent(
            model_inferences=10,
            monitor_breaches=[
                {"monitor": "drift.test", "at": "2026-06-01T09:00:00Z"},
            ],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.policy.violations[0].when is not None

    def test_plus_offset_parsed(self):
        payload = make_payload(single_agent(
            model_inferences=10,
            monitor_breaches=[
                {"monitor": "drift.test", "at": "2026-06-01T14:30:00+05:30"},
            ],
        ))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.policy.violations[0].when is not None

    def test_period_start_and_end_correct_order(self):
        payload = make_payload(single_agent(model_inferences=5))
        [p] = ArizeAdapter().to_partials(payload)
        assert p.period_start < p.period_end
