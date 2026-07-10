from __future__ import annotations

from ingestion import FieldMapping

YAML = """
constants:
  source: test_src

agent_id: $.id
agent_name: $.name
period_start: $.from
period_end: $.to

tasks:
  assigned: $.t.a
  completed: $.t.c
  failed: $.t.f

executions:
  attempts: $.e.a
  successful: $.e.s

policy:
  total_actions: $.p.n
  violations:
    _each: $.p.v[*]
    rule: $.r
    when: $.w

incidents:
  _each: $.i[*]
  severity_weight: $.sev
  frequency: $.freq
  source: $.src

quality:
  _optional: true
  accuracy: $.q.acc
  consistency: $.q.con
  hallucination_rate: $.q.hal

validation:
  required_components: $.v.r
  validated_components: $.v.v

cost:
  ai_cost_per_output: $.c.po
"""


def _payload(**overrides):
    base = {
        "id": "a1", "name": "A1",
        "from": "2026-06-01T00:00:00Z", "to": "2026-06-02T00:00:00Z",
        "t": {"a": 10, "c": 8, "f": 1},
        "e": {"a": 12, "s": 10},
        "p": {
            "n": 20,
            "v": [
                {"r": "rule.x", "w": "2026-06-01T01:00:00Z"},
                {"r": "rule.y", "w": "2026-06-01T02:00:00Z"},
            ],
        },
        "i": [
            {"sev": 0.5, "freq": 1, "src": "jira"},
        ],
        "q": {"acc": 0.9, "con": 0.85, "hal": 0.05},
        "v": {"r": 10, "v": 9},
        "c": {"po": 0.4},
    }
    base.update(overrides)
    return base


def test_round_trip_full_payload():
    obs = FieldMapping.from_string(YAML).apply(_payload())
    assert obs.agent_id == "a1"
    assert obs.source == "test_src"
    assert obs.tasks.assigned == 10
    assert obs.policy.total_actions == 20
    assert len(obs.policy.violations) == 2
    assert obs.policy.violations[0].rule == "rule.x"
    assert obs.incidents[0].severity_weight == 0.5
    assert obs.quality is not None
    assert obs.quality.accuracy == 0.9
    assert obs.validation.validated_components == 9


def test_optional_quality_collapses_to_none_when_absent():
    p = _payload()
    p.pop("q")  # no quality block at all
    obs = FieldMapping.from_string(YAML).apply(p)
    assert obs.quality is None


def test_each_with_empty_list_produces_empty():
    p = _payload()
    p["p"]["v"] = []
    p["i"] = []
    obs = FieldMapping.from_string(YAML).apply(p)
    assert obs.policy.violations == []
    assert obs.incidents == []
