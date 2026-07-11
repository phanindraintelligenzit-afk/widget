from __future__ import annotations

from ingestion import FieldMapping, GenericWebhookAdapter
from fixtures import load_raw, mapping_path


def test_acme_payload_through_generic_webhook():
    payload = load_raw("acme_payload")
    mapping = FieldMapping.from_yaml(mapping_path("acme"))
    obs_list = GenericWebhookAdapter(mapping).to_observations(payload)

    assert len(obs_list) == 1
    obs = obs_list[0]
    assert obs.agent_id == "acme-triage-42"
    assert obs.agent_name == "Acme Triage Bot"
    assert obs.source == "acme_agentops"
    assert obs.tasks.completed == 88
    assert obs.tasks.failed == 6
    assert obs.policy.total_actions == 200
    assert len(obs.policy.violations) == 2
    assert obs.policy.violations[0].rule == "pii.email_redaction"
    assert len(obs.incidents) == 2
    assert obs.quality is not None
    assert obs.quality.accuracy == 0.91
    assert obs.validation.validated_components == 9
    # The Cost contract carries just the three breakdown fields.
    # The engine derives the per-output figure at scoring time.
    assert obs.cost.model_cost == 33.0
    assert obs.cost.input_tokens == 240000
    assert obs.cost.output_tokens == 300000


def test_webhook_accepts_list_payload():
    payload = load_raw("acme_payload")
    mapping = FieldMapping.from_yaml(mapping_path("acme"))
    obs_list = GenericWebhookAdapter(mapping).to_observations([payload, payload])
    assert len(obs_list) == 2
    assert obs_list[0].agent_id == obs_list[1].agent_id
