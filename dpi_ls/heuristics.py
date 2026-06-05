"""Deterministic Q-dimension fallback used when the LLM evaluator is
unavailable (no AWS credentials, no model configured, or the call itself
fails for any reason).

The numbers produced here are *rough* — they exist so the demo doesn't
silently drop Q when the user has a fresh checkout and hasn't configured
Bedrock yet. The real Q signal should come from the LangGraph evaluator
or from the SME flow.

Heuristics (all in [0, 1]):

* accuracy
    Higher when the average output length is in a "reasonable" range
    (50–5000 chars) and the output doesn't look like a generic error
    message. Errors and very short outputs drag accuracy down.

* consistency
    Penalises output sets that disagree with themselves: high variance in
    length between successive outputs, or very different content in the
    first vs. last output. A single-output run returns 1.0 — there is
    no inconsistency to measure.

* hallucination_rate
    Returns 0.5 by default (the engine treats missing Q the same as
    "needs input" once it sees ``quality is None``; setting it to a
    concrete number only matters when an LLM was *supposed* to run but
    fell back to heuristics). We bias low for outputs that contain
    long paragraphs without concrete tokens (numbers, IDs, file paths)
    since those are the most common hallucination shape in practice.
"""
from __future__ import annotations

import re
from typing import Iterable


def heuristic_quality(outputs: Iterable[str]) -> dict[str, float]:
    """Return a {accuracy, consistency, hallucination_rate} triple."""
    out = [o for o in outputs if o]
    if not out:
        return {"accuracy": 0.0, "consistency": 1.0, "hallucination_rate": 0.5}

    lengths = [len(o) for o in out]
    avg_len = sum(lengths) / len(lengths)
    length_var = _variance(lengths)

    # --- accuracy: penalise error-shaped / very-short / very-long outputs
    bad = sum(1 for o in out if _looks_like_error(o))
    too_short = sum(1 for o in out if len(o) < 20)
    too_long = sum(1 for o in out if len(o) > 10_000)
    good = len(out) - bad - too_short - too_long
    accuracy = max(0.0, min(1.0, good / len(out)))

    # Bonus: being in the "reasonable" length band bumps accuracy.
    if 50.0 <= avg_len <= 5000.0:
        accuracy = min(1.0, accuracy + 0.05)

    # --- consistency: penalise length variance between outputs.
    # Variance of 0 → 1.0; huge variance → drop to ~0.5.
    if length_var < 1.0:
        consistency = 1.0
    else:
        # Normalise by the running mean so it scales with output size.
        rel_var = length_var / max(avg_len, 1.0) ** 2
        consistency = max(0.5, min(1.0, 1.0 - rel_var))

    # --- hallucination rate: low for outputs with concrete tokens,
    # higher for vague / hand-wavy text.
    concrete = 0
    for o in out:
        if _has_concrete_tokens(o):
            concrete += 1
    hallucination = 1.0 - (concrete / len(out))
    hallucination = max(0.0, min(1.0, hallucination))

    return {
        "accuracy": round(accuracy, 4),
        "consistency": round(consistency, 4),
        "hallucination_rate": round(hallucination, 4),
    }


def _variance(xs: list[int]) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    return sum((x - mean) ** 2 for x in xs) / len(xs)


_ERROR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:traceback \(most recent call last\):)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\b(?:unhandled\s+)?exception\b", re.IGNORECASE),
    re.compile(r"\b(?:internal\s+server\s+error|status\s+code\s+5\d\d)\b", re.IGNORECASE),
    re.compile(r"^\s*error[:\s]", re.IGNORECASE | re.MULTILINE),
)


def _looks_like_error(text: str) -> bool:
    return any(p.search(text) for p in _ERROR_PATTERNS)


_CONCRETE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{2,}\b"),                # multi-digit number
    re.compile(r"\b[A-Z]{2,}-\d+\b"),          # e.g. INC-1234, AWS-1234
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),  # IPv4
    re.compile(r"\b[A-Za-z0-9._/-]+\.(?:py|js|ts|json|yaml|yml|toml|md|csv)\b"),  # file path
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),  # uuid
)


def _has_concrete_tokens(text: str) -> bool:
    return any(p.search(text) for p in _CONCRETE_PATTERNS)
