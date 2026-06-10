"""Regex policy patterns for the G (governance) dimension.

Kept here — not in the engine — because the engine never inspects raw
text: it only ever sees ``obs.policy.violations`` as a list of (rule,
when) tuples. The collector runs these regexes on every output and
records the matched rules.

The patterns are intentionally conservative (we'd rather miss a real
violation than false-positive on a demo), and the list is the minimum
that a defence-in-depth run would actually want. New rules go in
``RULES`` and are picked up automatically.

The rule set is organised by namespace so the dashboard can group
violations by category::

    pii.*         — personal data leakage (email, phone, CC, SSN, PHI)
    secret.*      — credential leakage (AWS, bearer, generic api_key)
    prompt.*      — prompt-injection / jailbreak markers
    authz.*       — authorization failures (textual — runtime errors
                    are mapped in collector._ERROR_RULE_MAP)
    auth.*        — authentication failures
    audit.*       — audit-trail failures
    compliance.*  — regulatory / standards breaches
    dlp.*         — data-loss-prevention / exfiltration
    governance.*  — process-governance failures (missing approvals, etc.)

The collector deduplicates by rule within one output, so a paragraph
that contains two emails still emits exactly one ``pii.email``
violation. The ``_rules_for_text`` helper is the canonical scan entry
point — it returns the deduplicated set.
"""
from __future__ import annotations

import re
from typing import Iterable


# Each rule is a (rule_name, compiled_regex) pair. Order doesn't matter;
# the collector deduplicates by rule within one output.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ---- PII — personal data leakage --------------------------------
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
        # Two safe alternatives — avoids the catastrophic backtracking risk of
        # (?:\d[ -]*?){13,16} (lazy quantifier inside repetition).
        # Alt 1: 13–16 consecutive digits (no separators).
        # Alt 2: exactly the NNNN[- ]NNNN[- ]NNNN[- ]NNNN(NNN) formatted form.
        re.compile(
            r"\b\d{13,16}\b"
            r"|"
            r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{1,4}\b"
        ),
    ),
    (
        "pii.ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    # Medical Record Number — a clinical-PHI marker used by US/EU healthcare
    # systems. Catches "MRN 1234567" and "MRN:1234567" forms. 6-10 digits
    # matches the practical range used by Epic / Cerner / Allscripts.
    (
        "pii.mrn",
        re.compile(r"\bMRN[\s:#-]*\d{6,10}\b", re.IGNORECASE),
    ),
    # ---- Secrets — credential leakage ------------------------------
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
    # ---- Prompt injection / jailbreak -------------------------------
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
    # ---- Authorization (authz) — text-level signals -----------------
    # ``authz.permission_denied`` and ``authz.forbidden`` are kept here
    # because they name a concrete failure ("Permission denied" /
    # "403 forbidden") — a log line, an exception message, or a tool
    # result. They don't false-positive on prose that *discusses*
    # authorization (e.g. "we authorize payments").
    #
    # The two broader ``authz.unauthorized_data_access`` /
    # ``authz.unauthorized_system_access`` patterns that used to live
    # here were removed: they matched any prose containing the phrase
    # "unauthorized access" and so fired whenever an LLM mentioned
    # the topic naturally (FinOps agents describing IAM, security
    # post-mortems, compliance reports, etc.) — even when the agent's
    # code never raised an auth error. Real auth failures still get
    # tagged via the exception-class map in
    # ``collector._ERROR_RULE_MAP`` (``PermissionError`` /
    # ``AccessDenied`` / ``UnauthorizedError`` etc.) and via the
    # ``authz.permission_denied`` / ``authz.forbidden`` text rules
    # above when the message is a concrete failure line.
    (
        "authz.permission_denied",
        re.compile(r"\bpermission\s+denied\b", re.IGNORECASE),
    ),
    (
        "authz.forbidden",
        re.compile(r"\b(?:forbidden|access\s+is\s+denied|403\s+forbidden)\b",
                   re.IGNORECASE),
    ),
    # ---- Authentication (auth) failures -----------------------------
    (
        "auth.failed",
        re.compile(
            r"\b(?:authentication\s+failed|invalid\s+credentials|"
            r"login\s+failed|invalid\s+(?:username|password|token))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "auth.unauthorized",
        re.compile(
            r"\b(?:401\s+unauthor(?:ized|ised)|unauthor(?:ized|ised):\s+"
            r"authentication\s+required)\b",
            re.IGNORECASE,
        ),
    ),
    # ---- Audit-trail failures --------------------------------------
    # Catches "audit log write failed", "missing audit entry", "audit
    # log gap", and the more common "audit trail failure" phrasing
    # used in incident reports.
    (
        "audit.trail_failure",
        re.compile(
            r"\b(?:audit(?:\s+log)?\s+(?:write|failure|missing|gap|"
            r"disabled)|missing\s+audit\s+entry|audit\s+trail\s+"
            r"(?:failure|incomplete|missing))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "audit.unlogged_action",
        re.compile(
            r"\b(?:unlogged|unrecorded|untraced)\s+(?:action|operation|"
            r"request|call)\b",
            re.IGNORECASE,
        ),
    ),
    # ---- Process governance — approvals, tickets, change-control ----
    # A common compliance signal: an action that required an approval
    # ticket (CHG-/CRQ-/REQ-) but proceeded without one.
    (
        "governance.missing_approval",
        re.compile(
            r"\b(?:missing|absent|required|without|skipped|overrode)\s+"
            r"(?:approval|approvals)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "governance.approval_ticket_missing",
        re.compile(
            r"\bno\s+(?:approval\s+)?ticket\s+(?:on\s+file|provided|"
            r"attached|found)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "governance.unauthorized_change",
        re.compile(
            r"\b(?:unauthor(?:ized|ised)|unapproved)\s+(?:change|"
            r"modification|deployment|release|push)\b",
            re.IGNORECASE,
        ),
    ),
    # ---- Regulatory / compliance breaches --------------------------
    # Catches "HIPAA breach", "PHI breach", "SOX violation", "GDPR
    # breach", and the general "compliance breach" phrasing. The
    # regexes are anchored on the standards-name word to keep false
    # positives low.
    (
        "compliance.breach",
        re.compile(
            r"\b(?:hipaa|sox|gdpr|phi|pci|hippa|iso27001)\s+"
            r"(?:breach|violation|non[- ]compliance|noncompliance)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "compliance.breach_general",
        re.compile(
            r"\bcompliance\s+breach\b|\bregulatory\s+(?:breach|"
            r"violation)\b",
            re.IGNORECASE,
        ),
    ),
    # ---- DLP / data exfiltration -----------------------------------
    # Catches the common DLP-log phrasings: "data exfiltration",
    # "exfiltrated to", "uploaded to external", and "sent to external host".
    (
        "dlp.exfiltration",
        re.compile(
            r"\b(?:data\s+exfiltration|exfiltrat\w+(?:\s+(?:to|via))?|"
            r"uploaded\s+to\s+external|sent\s+to\s+external(?:\s+host)?|"
            r"unauthor(?:ized|ised)\s+(?:upload|transfer|export))\b",
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


# Backwards-compatible alias — some external callers (and the
# collector's tests) use the longer name.
_rules_for_text = scan_policy_violations
