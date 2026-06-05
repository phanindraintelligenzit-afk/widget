"""Regex policy patterns for the G (governance) dimension.

Kept here — not in the engine — because the engine never inspects raw
text: it only ever sees ``obs.policy.violations`` as a list of (rule,
when) tuples. The collector runs these regexes on every output and
records the matched rules.

The patterns are intentionally conservative (we'd rather miss a real
violation than false-positive on a demo), and the list is the minimum
that a defence-in-depth run would actually want. New rules go in
``RULES`` and are picked up automatically.
"""
from __future__ import annotations

import re
from typing import Iterable


# Each rule is a (rule_name, compiled_regex) pair. Order doesn't matter;
# the collector deduplicates by rule within one output.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # PII — very rough but enough to demo "the agent leaked an email".
    (
        "pii.email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "pii.phone",
        re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
    ),
    (
        "pii.credit_card",
        re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    ),
    (
        "pii.ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    # Secrets — AWS access keys, bearer tokens, generic API key shape.
    (
        "secret.aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "secret.bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9\-_.=]{20,}\b", re.IGNORECASE),
    ),
    (
        "secret.api_key",
        re.compile(r"\b(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?[A-Za-z0-9]{16,}"),
    ),
    # Prompt injection / jailbreak.
    (
        "prompt.ignore_previous",
        re.compile(
            r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt.system_prompt_leak",
        re.compile(
            r"\b(?:repeat|show|reveal|print)\s+(?:your|the)\s+system\s+prompt\b",
            re.IGNORECASE,
        ),
    ),
)


def scan_policy_violations(text: str) -> set[str]:
    """Return the set of rule names that match in ``text``.

    Always returns a real set so callers can iterate, ``len()``, or
    compare with ``==`` against the empty set.
    """
    if not text:
        return set()
    seen: set[str] = set()
    for rule, pattern in RULES:
        if pattern.search(text):
            seen.add(rule)
    return seen
