"""Tests for the deterministic Q fallback heuristic.

The heuristic is the safety net when the LangGraph evaluator isn't
available. It must always return three numbers in [0, 1] and never
crash on empty/weird inputs.
"""
from __future__ import annotations

import pytest

from dpi_ls.heuristics import heuristic_quality


def test_empty_outputs_returns_safe_defaults():
    q = heuristic_quality([])
    assert q == {"accuracy": 0.0, "consistency": 1.0, "hallucination_rate": 0.5}


def test_single_output_returns_full_consistency():
    q = heuristic_quality(["just one output"])
    assert q["consistency"] == 1.0


def test_error_text_drags_accuracy_down():
    q = heuristic_quality([
        "All good, here's the result.",
        "Traceback (most recent call last):\n  File x...",
        "Another fine response from the agent.",
    ])
    assert q["accuracy"] < 1.0


def test_concrete_tokens_reduce_hallucination_estimate():
    q = heuristic_quality([
        "Order #12345 was placed on 2024-01-15 for 9.99 USD.",
        "The file config.yaml has three lines.",
    ])
    assert q["hallucination_rate"] < 0.5


def test_vague_text_increases_hallucination_estimate():
    q = heuristic_quality([
        "I think this is fine, probably.",
        "Maybe you should look into that, or maybe not.",
        "It could be a thing, I'm not sure.",
    ])
    assert q["hallucination_rate"] > 0.3


def test_inconsistent_lengths_drag_consistency_down():
    q = heuristic_quality([
        "a" * 5,
        "b" * 5000,
        "c" * 10,
    ])
    # Big variance in length → consistency below 1.0.
    assert q["consistency"] < 1.0


def test_clipping_in_collector():
    """set_quality must clip values to [0, 1] so a flaky LLM call can't
    poison the canonical contract."""
    from dpi_ls import SignalCollector
    c = SignalCollector(agent_id="x", agent_name="x")
    c.set_quality(1.5, -0.2, 0.5)
    assert c.quality["accuracy"] == 1.0
    assert c.quality["consistency"] == 0.0
    assert c.quality["hallucination_rate"] == 0.5


def test_evaluator_falls_back_to_heuristic_without_env():
    """With no AWS creds at all, evaluate_quality should not raise —
    it falls back to the heuristic. We can't fully exercise the LLM
    path in CI, but the failure mode must be safe."""
    import os
    saved = {k: os.environ.pop(k, None) for k in (
        "MODEL_NAME", "BEDROCK_MODEL_ID", "AWS_DEFAULT_REGION", "AWS_REGION",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    )}
    try:
        # Force a clean env so boto3 can't find any default creds.
        for k in saved:
            os.environ[k] = ""
        from dpi_ls import evaluate_quality
        result = evaluate_quality(["Sample output for the agent."])
        # Either an LLM source returned a score, or we fell back to
        # the heuristic. Both are valid outcomes.
        assert result.source in ("llm", "heuristic")
        assert 0.0 <= result.accuracy <= 1.0
        assert 0.0 <= result.consistency <= 1.0
        assert 0.0 <= result.hallucination_rate <= 1.0
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
