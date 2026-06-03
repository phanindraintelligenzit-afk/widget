"""Pure state-machine tests — no I/O, no DB."""
from __future__ import annotations

import pytest

from engine import sme_flow


def _walk(values):
    s = sme_flow.start("agent-x", "qa@example.com")
    for v in values:
        s = sme_flow.advance(s, v)
    return s


def test_happy_path_through_review_yes():
    s = _walk(["93", "91", "5", "yes"])
    assert sme_flow.is_complete(s)
    assert sme_flow.is_committed(s)
    assert s.accuracy == 0.93
    assert s.consistency == 0.91
    assert s.hallucination_rate == 0.05
    assert s.error is None


def test_unit_inputs_also_work():
    s = _walk(["0.93", "0.91", "0.05", "yes"])
    assert s.accuracy == 0.93


def test_percent_sign_stripped():
    s = _walk(["93%", "91%", "5%", "yes"])
    assert s.consistency == 0.91


def test_review_no_aborts_without_persistence():
    s = _walk(["93", "91", "5", "no"])
    assert sme_flow.is_complete(s)
    assert not sme_flow.is_committed(s)
    assert s.aborted is True


def test_invalid_number_stays_on_step():
    s = sme_flow.start("a", "qa")
    s = sme_flow.advance(s, "not a number")
    assert s.step == sme_flow.STEP_ASK_ACCURACY
    assert s.error is not None
    assert s.accuracy is None
    assert s.history == []  # the bad attempt was rolled back


def test_out_of_range_rejected():
    s = sme_flow.start("a", "qa")
    s = sme_flow.advance(s, "150")
    assert s.step == sme_flow.STEP_ASK_ACCURACY
    assert "between 0 and 100" in (s.error or "")


def test_review_requires_yes_or_no():
    s = _walk(["93", "91", "5"])
    s = sme_flow.advance(s, "maybe")
    assert s.step == sme_flow.STEP_REVIEW
    assert "yes" in (s.error or "")


def test_advance_after_done_raises_via_error_field():
    s = _walk(["93", "91", "5", "yes"])
    s = sme_flow.advance(s, "anything")
    assert s.error == "session already complete"


def test_start_requires_ids():
    with pytest.raises(sme_flow.SMEFlowError):
        sme_flow.start("", "qa")
    with pytest.raises(sme_flow.SMEFlowError):
        sme_flow.start("a", "")


def test_prompts_defined_for_every_step():
    for step in (
        sme_flow.STEP_ASK_ACCURACY,
        sme_flow.STEP_ASK_CONSISTENCY,
        sme_flow.STEP_ASK_HALLUCINATION,
        sme_flow.STEP_REVIEW,
        sme_flow.STEP_DONE,
    ):
        assert sme_flow.PROMPTS[step]
