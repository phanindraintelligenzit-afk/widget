"""Enterprise Validation dimension — Guardrails AI / Pydantic AI / Instructor.

Covers:
* Collector accepts events, never fabricates.
* Canonical normalization dedupes across adapters.
* Formula stays V = Validated Components / Required Components.
* Compliance gate fires at V < 0.60.
* API endpoints round-trip cleanly.
* Seeder writes the persisted evaluation rows and reflects live signal.
"""
from __future__ import annotations

import pytest


# ---- Collector-level behaviour (pure Python, no DB) ---------------------

def test_collector_starts_empty():
    from dpi_ls.enterprise_validation_evaluation_service import (
        reset_enterprise_validation_collector,
        get_enterprise_validation_collector,
    )
    reset_enterprise_validation_collector()
    c = get_enterprise_validation_collector()
    assert c.events() == []
    assert c.summarize() == {}
    dpi = c.dpi_ls_metrics()
    assert dpi == {
        "required_components": 0,
        "validated_components": 0,
        "validation_score": 0.0,
        "unsafe": False,
    }


def test_collector_records_events_never_fabricates():
    from dpi_ls.enterprise_validation_evaluation_service import (
        ValidationEvent,
        reset_enterprise_validation_collector,
        get_enterprise_validation_collector,
    )
    reset_enterprise_validation_collector()
    c = get_enterprise_validation_collector()
    c.record(ValidationEvent(adapter="Guardrails AI", kind="json", passed=True, latency_ms=10.0))
    c.record(ValidationEvent(adapter="Pydantic AI", kind="schema", passed=True, latency_ms=5.0))
    c.record(ValidationEvent(adapter="Pydantic AI", kind="schema", passed=False, latency_ms=15.0, retries=2))
    events = c.events()
    assert len(events) == 3
    # No other adapters materialise.
    summary = c.summarize()
    assert set(summary) == {"Guardrails AI", "Pydantic AI"}


def test_dpi_ls_formula_holds_v_equals_validated_over_required():
    """The DPI-LS Validation formula must remain mathematically identical."""
    from dpi_ls.enterprise_validation_evaluation_service import (
        ValidationEvent,
        reset_enterprise_validation_collector,
        get_enterprise_validation_collector,
    )
    reset_enterprise_validation_collector()
    c = get_enterprise_validation_collector()
    # 4 distinct kinds attempted, 3 distinct kinds passed → V = 3/4 = 0.75
    for kind, passed in [
        ("json",   True),
        ("schema", True),
        ("type",   True),
        ("regex",  False),
    ]:
        c.record(ValidationEvent(adapter="Guardrails AI", kind=kind, passed=passed))
    dpi = c.dpi_ls_metrics()
    assert dpi["required_components"] == 4
    assert dpi["validated_components"] == 3
    assert dpi["validation_score"] == 0.75
    assert dpi["unsafe"] is False


def test_compliance_gate_fires_below_0_60():
    """Hard gate — V < 0.60 must flip unsafe=True."""
    from dpi_ls.enterprise_validation_evaluation_service import (
        ValidationEvent,
        reset_enterprise_validation_collector,
        get_enterprise_validation_collector,
    )
    reset_enterprise_validation_collector()
    c = get_enterprise_validation_collector()
    # 5 distinct kinds attempted, 2 distinct kinds passed → V = 2/5 = 0.40 < 0.60
    for kind, passed in [
        ("json",     True),
        ("schema",   True),
        ("type",     False),
        ("field",    False),
        ("required", False),
    ]:
        c.record(ValidationEvent(adapter="Pydantic AI", kind=kind, passed=passed))
    dpi = c.dpi_ls_metrics()
    assert dpi["validation_score"] == 0.40
    assert dpi["unsafe"] is True


def test_canonical_normalisation_dedupes_across_adapters():
    """The three adapters emit different native names for the same
    concept. Canonical rollup must merge without duplication."""
    from dpi_ls.enterprise_validation_evaluation_service import (
        CANONICAL_MAP,
        ValidationEvent,
        reset_enterprise_validation_collector,
        get_enterprise_validation_collector,
    )
    reset_enterprise_validation_collector()
    c = get_enterprise_validation_collector()

    # All three adapters emit their JSON-compliance native metric.
    c.record(ValidationEvent(adapter="Guardrails AI", kind="json_validation", passed=True))
    c.record(ValidationEvent(adapter="Pydantic AI",   kind="json_success",    passed=True))
    c.record(ValidationEvent(adapter="Instructor",    kind="json_parsing",    passed=True))

    canonical = c.canonical()
    assert "json_compliance" in canonical
    assert set(canonical["json_compliance"]["sources"]) == {
        "Guardrails AI", "Pydantic AI", "Instructor",
    }
    # Ensure CANONICAL_MAP intentionally does not contain
    # per-adapter duplicate keys.
    assert "json_success" not in canonical
    assert "json_parsing" not in canonical
    assert "json_validation" not in canonical


# ---- API round-trip (uses the shared FastAPI test client fixture) -----

def test_urls_endpoint_returns_three_adapters(client):
    r = client.get("/api/enterprise-validation/urls")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"Guardrails AI", "Pydantic AI", "Instructor"}
    for name, info in data.items():
        assert info["url"].startswith("https://")
        assert "online" in info
        assert "sdk_available" in info


def test_open_resource_urls_point_to_official_documentation(client):
    r = client.get("/api/enterprise-validation/urls").json()
    assert r["Guardrails AI"]["url"] == "https://www.guardrailsai.com/docs"
    assert r["Pydantic AI"]["url"]   == "https://ai.pydantic.dev"
    assert r["Instructor"]["url"]    == "https://python.useinstructor.com"


def test_push_endpoint_records_event_and_updates_persistence(client):
    from dpi_ls.enterprise_validation_evaluation_service import (
        reset_enterprise_validation_collector,
    )
    reset_enterprise_validation_collector()

    r = client.post("/api/enterprise-validation/push", json={
        "adapter": "Guardrails AI",
        "kind":    "json_validation",
        "expected": '{"a": 1}',
        "actual":   '{"a": 1}',
        "passed":  True,
        "retries": 0,
        "latency_ms": 12.5,
        "correlation_id": "req-abc",
    })
    assert r.status_code == 200
    assert r.json()["recorded"] is True

    results = client.get("/api/enterprise-validation/results").json()
    # There should be at least one Guardrails row now with agent_executed=True.
    ga_live = [row for row in results
               if row["resource_name"] == "Guardrails AI" and row["agent_executed"]]
    assert ga_live, "expected at least one live Guardrails AI evaluation row"


def test_push_rejects_missing_adapter_or_kind(client):
    assert client.post("/api/enterprise-validation/push", json={"adapter": "X"}).status_code == 400
    assert client.post("/api/enterprise-validation/push", json={"kind": "json"}).status_code == 400


def test_agent_dashboard_exposes_formula_and_gate(client):
    """The Agent Dashboard endpoint must publish the formula, weights,
    canonical metrics, match analysis, and compliance-gate state."""
    from dpi_ls.enterprise_validation_evaluation_service import (
        reset_enterprise_validation_collector,
    )
    reset_enterprise_validation_collector()

    # Push a failing scenario: 1 pass + 2 fails → V = 1/3 = 0.333 → unsafe.
    for kind, passed in [("json", True), ("schema", False), ("type", False)]:
        client.post("/api/enterprise-validation/push", json={
            "adapter": "Pydantic AI", "kind": kind, "passed": passed,
        })

    r = client.get("/api/enterprise-validation/agent-dashboard").json()
    assert r["formula"] == "V = Validated Components / Required Components"
    assert r["required_components"] == 3
    assert r["validated_components"] == 1
    assert r["validation_score"] == round(1/3, 4)
    gate = r["compliance_gate"]
    assert gate["threshold"] == 0.60
    assert gate["triggered"] is True
    assert gate["unsafe"] is True
    assert gate["capped_score"] == 69
    assert isinstance(r["match_analysis"], list)
    assert len(r["match_analysis"]) == 3
    assert isinstance(r["canonical_metrics"], dict)
    adapters = {a["name"] for a in r["adapters"]}
    assert adapters == {"Guardrails AI", "Pydantic AI", "Instructor"}


def test_seeder_registers_three_resources(client):
    """Bootstrap must have registered the 3 enterprise validation resources
    even before any events are pushed."""
    resources = client.get("/api/enterprise-validation/resources").json()
    names = {r["resource_name"] for r in resources}
    assert names == {"Guardrails AI", "Pydantic AI", "Instructor"}
    # Every one carries a real documentation URL.
    for r in resources:
        assert r["documentation_url"].startswith("https://")


def test_evaluate_endpoint_is_idempotent(client):
    """Calling /evaluate twice should not create duplicate rows —
    the seeder purges non-agent baseline rows on every run."""
    r1 = client.post("/api/enterprise-validation/evaluate").json()
    r2 = client.post("/api/enterprise-validation/evaluate").json()
    # Same row count both times.
    assert len(r1) == len(r2)


# ---- DPI-LS formula must remain unchanged ------------------------------

def test_dpi_ls_v_formula_unchanged():
    """Extending the Validation dimension must NOT modify the DPI-LS
    engine's compute_V formula."""
    from engine.metrics import compute_V
    # Spec: V = validated / required, gated below 1.0
    assert compute_V(validated=6, required=8) == 0.75
    assert compute_V(validated=0, required=1) == 0.0
    assert compute_V(validated=1, required=1) == 1.0
    # Vacuously safe when required=0.
    assert compute_V(validated=0, required=0) == 1.0
