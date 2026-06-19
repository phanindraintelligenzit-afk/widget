"""Runtime signal collector for the 7 DPI-LS dimensions.

The collector accumulates raw signals from whichever framework
``monitor()`` ended up instrumenting. It is intentionally framework-agnostic:
a frame-specific patcher (see ``frameworks/``) calls into these methods
when it sees an LLM call, a tool call, an exception, or a final output.

At finalize time the collector turns its accumulated state into a
canonical ``AgentObservation`` that the existing DPI-LS engine scores.
Six of the seven dimensions are derived deterministically here; Q is
filled in by the LangGraph evaluator (``evaluator.py``) which calls
``set_quality()`` once the LLM is done.

The collector is the single source of truth for the in-process session —
it is shared across all framework patchers via the global state in
``_state.py``.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from .policy import scan_policy_violations
from .risk import scan_lakera_risks

# Global thread pool for async Lakera Guard risk scanning
_risk_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dpi_risk_scan")

# Cap how many full outputs we keep for the LLM evaluator. The last N are
# the most representative of how the run actually ended, and feeding the
# full conversation into three LLM calls is wasteful.
_MAX_OUTPUTS_FOR_Q = 6

# Max source-data items passed to the hallucination evaluator.
# Source data = input queries + tool results the agent had access to.
_MAX_SOURCE_DATA = 8

# Output kind constants — stored alongside each captured output.
_KIND_AGENT = "agent"   # LLM-generated prose / structured answer
_KIND_TOOL  = "tool"    # raw tool result (API response, DB row, etc.)

# Cap the total buffer for outputs to keep memory bounded for very long
# agent runs.
_MAX_OUTPUT_BUFFER = 64


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SignalCollector:
    """Aggregates raw signals from a single instrumented agent run.

    The instance is created when ``monitor()`` is called and lives until
    the process exits. ``finalize()`` is the one place that turns the
    accumulated state into an ``AgentObservation``.
    """

    agent_id: str
    agent_name: str
    framework: str = "unknown"

    # Optional per-agent human baseline (outputs/period). When set, the
    # poster will update the agent row in the DB so P is computed against
    # the right denominator. None means "use the DB row's existing value".
    human_baseline: Optional[int] = None

    # Wall-clock bounds of the run.
    period_start: datetime = field(default_factory=_utcnow)
    period_end: Optional[datetime] = None

    # Output buffer (string bodies, in arrival order). Last N are sent to
    # the Q evaluator.
    _outputs: list[str] = field(default_factory=list)
    _output_kinds: list[str] = field(default_factory=list)  # parallel list: "agent" | "tool"
    _outputs_lock: threading.Lock = field(default_factory=threading.Lock)

    # E — execution. attempts = total LLM/tool calls, successful = those
    # that didn't raise, failed = those that did.
    attempts: int = 0
    successful: int = 0
    failed: int = 0
    execution_details: list[dict] = field(default_factory=list)

    # P — agent-level run counter. Each time the agent completes a full
    # invocation (Runner.run returns, Crew kicks off, etc.) this is +1.
    # It is separate from LLM-level attempts so P measures agent runs,
    # not individual LLM calls inside one run.
    agent_runs_completed: int = 0
    agent_runs_failed: int = 0

    # G — governance. Each violation is a (rule, when) tuple.
    violations: list[dict] = field(default_factory=list)
    policy_evaluations: int = 0

    # R — risk. Each incident is a (severity_weight, frequency, source).
    incidents: list[dict] = field(default_factory=list)

    # C — cost. Tokens in/out summed across calls; cloud cost approximated
    # by token price × tokens; ``systems_accessed`` is a de-duped set of
    # base URLs the agent called against.
    tokens_in: int = 0
    tokens_out: int = 0
    cloud_cost: float = 0.0
    llm_calls: int = 0
    human_cost: float = 0.0
    _systems_accessed: set[str] = field(default_factory=set)

    # V — validation. We treat any output that looks like a structured
    # payload (valid JSON, has "answer"/"result" key, or matches the
    # required-schema spec) as validated. The collector does best-effort
    # heuristics, not a real schema validator.
    validated_outputs: int = 0
    total_outputs: int = 0

    # RAG-specific signals — populated by the LlamaIndex and RAG patchers
    # via ``record_retrieval``. A retrieval counts as one E-relevant
    # execution (it's a tool call) but is tracked separately so the
    # per-agent card can show "N retrievals · M docs" underneath E.
    retrievals: int = 0
    retrieved_docs_total: int = 0
    last_retrieval_top_score: float = 0.0

    # Q — quality. Set by the LangGraph evaluator after the run finishes.
    quality: Optional[dict] = None  # {accuracy, consistency, hallucination_rate}

    # Source data for hallucination detection — the input task / retrieved
    # documents / tool results the agent had access to during the run.
    # Populated by framework patchers (auto, from invoke args) and by the
    # user via ``collector.record_source(text)`` for explicit control.
    _source_data: list[str] = field(default_factory=list)
    _source_data_lock: threading.Lock = field(default_factory=threading.Lock)

    # Lock for the small handful of counters that are incremented from
    # background threads (uvicorn server thread + main thread both touch
    # the collector when the engine talks back during /ingest).
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ---- recording API (called by framework patchers) -----------------

    def record_llm_call(
        self,
        output: str,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0,
        system: str | None = None,
        ok: bool = True,
        action_name: str | None = None,
    ) -> None:
        """One LLM call completed. Records tokens/cost/output for Q."""
        with self._lock:
            self.attempts += 1
            self.llm_calls += 1
            if ok:
                self.successful += 1
            else:
                self.failed += 1
            self.tokens_in += int(tokens_in or 0)
            self.tokens_out += int(tokens_out or 0)
            self.cloud_cost += float(cost or 0.0)
            if action_name:
                self.execution_details.append({"name": action_name, "ok": ok})
        if output:
            self._capture_output(output, system=system)

    def record_source(self, text: str, *, kind: str = "input") -> None:
        """Record source data used as ground truth for hallucination detection.

        Call this with:
        * The task / question sent to the agent (``kind="input"``).
        * Relevant retrieved documents (``kind="retrieved"``).
        * Key tool results (``kind="tool_result"``).

        Framework patchers call this automatically with the first argument
        passed to ``invoke``/``ainvoke``. Agent code can also call it
        explicitly for finer control.

        Args:
            text: The source text to record.
            kind: Label (``"input"``, ``"retrieved"``, ``"tool_result"``).
        """
        if not text or not text.strip():
            return
        # Prefix each item with its kind so the evaluator can distinguish
        # the original task from retrieved documents.
        labelled = f"[{kind.upper()}]\n{text.strip()}"
        with self._source_data_lock:
            self._source_data.append(labelled)
            if len(self._source_data) > _MAX_SOURCE_DATA:
                del self._source_data[: len(self._source_data) - _MAX_SOURCE_DATA]
                
        # R: Asynchronous Lakera Guard scan on source inputs (catches prompt injections/jailbreaks)
        def _scan_and_record():
            incidents = scan_lakera_risks(text)
            if incidents:
                with self._lock:
                    self.incidents.extend(incidents)
        
        _risk_executor.submit(_scan_and_record)

    def record_tool_call(self, *, ok: bool = True, action_name: str | None = None) -> None:
        with self._lock:
            self.attempts += 1
            if ok:
                self.successful += 1
            else:
                self.failed += 1
            if action_name:
                self.execution_details.append({"name": action_name, "ok": ok})

    def record_retrieval(
        self,
        *,
        docs_count: int = 0,
        top_score: float = 0.0,
        ok: bool = True,
    ) -> None:
        """A retriever returned ``docs_count`` documents.

        Drives E (a retrieval IS an execution) and surfaces two
        per-agent-card signals: ``retrievals`` (call count) and
        ``retrieved_docs_total`` (sum of node counts). The retrieved
        text itself is captured separately by the caller via
        ``_capture_output(..., kind="tool")`` so V and G see it but
        the Q LLM evaluator does not.
        """
        with self._lock:
            if ok:
                self.attempts += 1
                self.successful += 1
            else:
                self.attempts += 1
                self.failed += 1
            self.retrievals += 1
            self.retrieved_docs_total += max(0, int(docs_count))
            if top_score:
                self.last_retrieval_top_score = float(top_score)

    def record_agent_run(self, *, ok: bool = True) -> None:
        """Called when a top-level agent run completes (or fails).

        This drives P: one completed run = one unit of AI output for
        the productivity numerator. For multi-run scripts this accumulates
        across all invocations.
        """
        with self._lock:
            if ok:
                self.agent_runs_completed += 1
            else:
                self.agent_runs_failed += 1

    def record_error(self, exc: BaseException, *, source: str = "agent") -> None:
        """An exception surfaced during the run. Drives R + G."""
        with self._lock:
            self.attempts += 1
            self.failed += 1
        # Severity weights: rough mapping; the real R calc in the engine
        # normalises against settings.r_max.
        sev = 1.0 if isinstance(exc, (TimeoutError, ConnectionError)) else 0.5
        self.incidents.append(
            {"severity_weight": sev, "frequency": 1, "source": source}
        )
        # Most errors are also policy/action events in spirit; if the
        # error name maps to a known rule, surface it as a violation too.
        rule = _error_to_rule(exc)
        if rule:
            self.violations.append(
                {"rule": rule, "when": _utcnow().isoformat()}
            )

    def record_systems_accessed(self, base_url: str) -> None:
        if base_url:
            self._systems_accessed.add(base_url)

    def set_quality(
        self,
        accuracy: float,
        consistency: float,
        hallucination_rate: float,
    ) -> None:
        """Called by the LangGraph evaluator once it's done."""
        # Clip to [0, 1] so a poorly-prompted LLM can't poison Q.
        self.quality = {
            "accuracy": max(0.0, min(1.0, float(accuracy))),
            "consistency": max(0.0, min(1.0, float(consistency))),
            "hallucination_rate": max(0.0, min(1.0, float(hallucination_rate))),
        }

    def mark_end(self) -> None:
        """Called by the atexit finalizer so the observation's period is correct."""
        if self.period_end is None:
            self.period_end = _utcnow()
            
        # Ensure all pending Lakera Guard async scans complete before finalizing
        _risk_executor.shutdown(wait=True)

    # ---- accessors used by finalize() ---------------------------------

    def source_data_for_q(self) -> list[str]:
        """Return the recorded source data items for the hallucination evaluator.

        Returns an empty list when no source data was captured — the
        evaluator falls back to the no-context hallucination prompt.
        """
        with self._source_data_lock:
            return list(self._source_data[-_MAX_SOURCE_DATA:])

    def outputs_for_q(self) -> list[str]:
        """The last N *agent* outputs (prose/analysis), in order, for the LLM evaluator.

        Tool results (raw API JSON) are intentionally excluded: the LLM
        cannot verify factual accuracy of external API data and consistently
        scored hallucination at 0.5 when raw JSON was mixed with prose.
        Falls back to all outputs if no agent-tagged outputs exist (e.g.
        unknown framework that doesn't distinguish the two).
        """
        with self._outputs_lock:
            agent_outputs = [
                text for text, kind in zip(self._outputs, self._output_kinds)
                if kind == _KIND_AGENT
            ]
            if agent_outputs:
                return agent_outputs[-_MAX_OUTPUTS_FOR_Q:]
            # Fallback: no kind tagging — return last N as before.
            return list(self._outputs[-_MAX_OUTPUTS_FOR_Q:])

    def _capture_output(
        self,
        output: str,
        *,
        system: str | None = None,
        kind: str = _KIND_AGENT,
    ) -> None:
        """Record one output and run deterministic G/V checks on it.

        Args:
            output: The text of the output.
            system: Optional label (e.g. the tool name). Used for logging.
            kind:   ``'agent'`` for LLM-generated prose/answers (used by Q),
                    ``'tool'`` for raw tool results (used only for G/V).
        """
        if not output:
            return
        with self._outputs_lock:
            self._outputs.append(output)
            self._output_kinds.append(kind)
            if len(self._outputs) > _MAX_OUTPUT_BUFFER:
                # Drop the oldest so memory doesn't grow on long runs.
                del self._outputs[: len(self._outputs) - _MAX_OUTPUT_BUFFER]
                del self._output_kinds[: len(self._output_kinds) - _MAX_OUTPUT_BUFFER]
        with self._lock:
            self.total_outputs += 1

        if kind == _KIND_AGENT:
            # G: deterministic policy scan over the output text.
            rules = scan_policy_violations(output)
            action_label = system if system else "LLM Generation"
            
            with self._lock:
                self.policy_evaluations += 1
                now = _utcnow().isoformat()
                if rules:
                    for rule in rules:
                        self.violations.append({"rule": rule, "when": now, "action_name": action_label})
                else:
                    self.violations.append({"rule": "none", "when": now, "action_name": action_label})

            # R: Asynchronous Lakera Guard scan on outputs (catches PII/Toxicity)
            def _scan_and_record():
                incidents = scan_lakera_risks(output)
                if incidents:
                    with self._lock:
                        self.incidents.extend(incidents)
            
            _risk_executor.submit(_scan_and_record)
        # V: best-effort structural check.
        if _looks_structured(output):
            with self._lock:
                self.validated_outputs += 1

    # ---- build the canonical observation ------------------------------

    def to_observation(self) -> dict[str, Any]:
        """Turn the accumulated state into a JSON-ready AgentObservation dict.

        Returns a plain dict (not the Pydantic model) so the poster can
        hand it to httpx as JSON; the API will validate it on the way in.
        """
        self.mark_end()
        end = self.period_end or _utcnow()
        start = self.period_start

        # P numerator: number of complete agent runs. Falls back to 1 if
        # the framework patcher signalled at least one successful execution
        # (meaning Runner.run returned OK at least once). This prevents
        # P=0 for single-run agents when record_agent_run wasn't called.
        completed_runs = self.agent_runs_completed
        if completed_runs == 0 and self.successful > 0:
            completed_runs = 1
        failed_runs = self.agent_runs_failed
        assigned_runs = completed_runs + failed_runs
        if assigned_runs == 0 and self.attempts > 0:
            assigned_runs = max(1, self.attempts)

        # E — execution efficiency: successful LLM+tool calls / attempts.
        # Keep raw signal counts for E; don't conflate with agent runs.

        # C — cost per agent run output (not per LLM call).
        # ``model_cost`` is the raw total the LLM calls reported.
        # If no real cost was reported we fall back to a token-based
        # estimate so the dimension has something to score against.
        # The engine derives the per-output figure
        # (``model_cost / completed_outputs``) itself; we just carry
        model_cost = self.cloud_cost
        if model_cost == 0.0 and (self.tokens_in + self.tokens_out) > 0:
            import os
            model_id = os.getenv("BEDROCK_MODEL_ID", "")
            if model_id:
                try:
                    from .cost_calculator import BedrockDynamicCostCalculator
                    global _cost_calculator
                    if '_cost_calculator' not in globals():
                        _cost_calculator = BedrockDynamicCostCalculator()
                    model_cost = _cost_calculator.calculate_cost(self.tokens_in, self.tokens_out, model_id)
                except Exception as e:
                    pass

            if model_cost == 0.0:
                # Conservative blended estimate: $0.001 per 1k tokens
                model_cost = (self.tokens_in + self.tokens_out) * 0.000001

        # V — validation: fraction of captured outputs that look structured.
        # Use total_outputs as the required count; if zero but we had
        # attempts, treat attempts as required so V isn't vacuously 1.0.
        required = self.total_outputs
        if required == 0 and self.attempts > 0:
            required = self.attempts
        validated = self.validated_outputs

        # Aggregate incidents by source and severity bucket
        aggregated_incidents = {}
        for inc in self.incidents:
            sev = float(inc.get("severity_weight", 0.2))
            if sev >= 0.7:
                bucket = "High"
            elif sev >= 0.3:
                bucket = "Medium"
            else:
                bucket = "Low"
                
            key = (inc.get("source"), bucket)
            if key not in aggregated_incidents:
                aggregated_incidents[key] = inc.copy()
            else:
                existing = aggregated_incidents[key]
                old_freq = existing.get("frequency", 1)
                old_sev = float(existing.get("severity_weight", 0))
                
                new_freq = inc.get("frequency", 1)
                new_sev = sev
                
                total_freq = old_freq + new_freq
                avg_sev = ((old_freq * old_sev) + (new_freq * new_sev)) / total_freq
                
                existing["frequency"] = total_freq
                existing["severity_weight"] = avg_sev
                
        obs: dict[str, Any] = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name or self.agent_id,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "tasks": {
                "assigned": assigned_runs,
                "completed": completed_runs,
                "failed": failed_runs,
            },
            "executions": {
                "attempts": self.attempts,
                "successful": self.successful,
                "details": self.execution_details,
            },
            "policy": {
                "total_actions": max(self.policy_evaluations, 1),
                "violations": self.violations,
            },
            "incidents": list(aggregated_incidents.values()),
            "validation": {
                "required_components": required,
                "validated_components": validated,
                "audit_ready": required > 0 and validated >= required,
            },
            "cost": {
                # The three fields the per-agent card's C panel
                # renders. The engine derives the per-output figure
                # from ``model_cost / tasks.completed`` internally —
                # the observation never carries the derived value.
                "input_tokens": self.tokens_in,
                "output_tokens": self.tokens_out,
                "model_cost": model_cost,
                "number_of_llm_calls": self.llm_calls,
                "Human_cost": self.human_cost,
            },
            "source": f"dpi_ls:{self.framework}",
            # RAG signals — observed by the LlamaIndex / RAG patchers.
            "retrievals": self.retrievals,
            "retrieved_docs_total": self.retrieved_docs_total,
        }
        if self.quality is not None:
            obs["quality"] = self.quality
        return obs

    # ---- snapshot for debugging ---------------------------------------

    def summary(self) -> dict[str, Any]:
        """One-line human summary of the run."""
        return {
            "agent_id": self.agent_id,
            "framework": self.framework,
            "attempts": self.attempts,
            "successful": self.successful,
            "violations": len(self.violations),
            "incidents": len(self.incidents),
            "tokens": self.tokens_in + self.tokens_out,
            "outputs": self.total_outputs,
            "validated": self.validated_outputs,
            "retrievals": self.retrievals,
            "retrieved_docs_total": self.retrieved_docs_total,
            "has_quality": self.quality is not None,
        }


# ---------------------------------------------------------------------------
# Helpers — small, private, kept here because they belong to the collector
# ---------------------------------------------------------------------------

_VALIDATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Strict JSON object or array — canonical structured output.
    re.compile(r"^\s*\{[\s\S]*\}\s*$"),
    re.compile(r"^\s*\[[\s\S]*\]\s*$"),
    # XML / HTML-ish semantic tags wrapping an answer.
    re.compile(r"<\s*(answer|result|response|output)\s*>", re.IGNORECASE),
    # Markdown fenced code or JSON codeblock.
    re.compile(r"```(?:json|yaml|toml|csv)?\s*[\s\S]+```"),
)

# Patterns that use .search() — they can appear ANYWHERE in the text,
# not just at the start. These must NOT use ^ anchoring with .match().
_VALIDATION_SEARCH_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Markdown table — a line with at least one | separator column.
    # e.g.  | Region | Cost |  or  |--------|------|
    re.compile(r"^\|.+\|.+\|", re.MULTILINE),
    # Markdown report with section headers (## or ###) — a structured analysis.
    re.compile(r"^#{2,3}\s+\S", re.MULTILINE),
)


def _looks_structured(text: str) -> bool:
    if not text:
        return False
    s = text.strip()
    if not s:
        return False
    # Whole-string patterns: .match() anchors to the start.
    for pat in _VALIDATION_PATTERNS:
        if pat.match(s):
            return True
    # Anywhere patterns: .search() scans the full text.
    for pat in _VALIDATION_SEARCH_PATTERNS:
        if pat.search(s):
            return True
    return False

# Some error names map cleanly to a policy rule. The table covers the
# common SDK exception classes (AWS / Azure / GCP / boto3 / httpx /
# requests / OpenAI / Anthropic / aiohttp) plus the framework-specific
# subclasses the package's own patchers raise. Anything else falls
# through to the soft-check on the message — see ``_error_to_rule``.
#
# Why the table is the canonical path: a textual match on the message
# is brittle (one vendor says "AccessDenied", another says "Forbidden",
# a third says "403"). The class name is the contract the user agreed
# to when they caught the exception. New exception classes go here.
_ERROR_RULE_MAP: dict[str, str] = {
    # ----- Authorization (authz) -----
    "PermissionDeniedError": "authz.permission_denied",
    "PermissionError": "authz.permission_denied",  # builtin
    "UnauthorizedError": "authz.unauthorized_data_access",
    "Forbidden": "authz.forbidden",
    "AccessDenied": "authz.forbidden",
    "AccessDeniedException": "authz.forbidden",
    # ----- Authentication (auth) -----
    "AuthenticationError": "auth.failed",
    "AuthError": "auth.failed",
    "InvalidCredentials": "auth.failed",
    "InvalidToken": "auth.failed",
    "TokenExpired": "auth.failed",
    # ----- Quota / rate limiting -----
    "RateLimitError": "quota.rate_limited",
    "RateLimitExceeded": "quota.rate_limited",
    "TooManyRequests": "quota.rate_limited",
    "ThrottlingException": "quota.rate_limited",
    # ----- Privacy / leakage -----
    "PiiLeakageError": "pii.leakage",
    "PIILeakageError": "pii.leakage",
    "PHILeakageError": "pii.phi",
    "DataLeakageError": "dlp.exfiltration",
    "DataExfiltrationError": "dlp.exfiltration",
    # ----- Compliance / governance -----
    "ComplianceViolation": "compliance.breach",
    "ComplianceViolationError": "compliance.breach",
    "RegulatoryViolation": "compliance.breach",
    "ApprovalRequiredError": "governance.missing_approval",
    "MissingApprovalError": "governance.missing_approval",
    "ChangeControlViolation": "governance.unauthorized_change",
    # ----- Audit trail -----
    "AuditTrailError": "audit.trail_failure",
    "AuditLogWriteError": "audit.trail_failure",
}


# Soft check: keywords we look for in the exception message when the
# class name isn't in ``_ERROR_RULE_MAP``. Each entry is (substring,
# rule). Substring matches are case-insensitive. Order matters — the
# first match wins. Keep these phrases narrow: false positives on
# governance rules are worse than misses, and the engine's gate fires
# on a single match.
_MESSAGE_RULE_HINTS: tuple[tuple[str, str], ...] = (
    ("pii", "pii.leakage"),
    ("redact", "pii.leakage"),
    ("phi", "pii.phi"),
    ("unauthor", "authz.unauthorized_data_access"),
    ("permission denied", "authz.permission_denied"),
    ("forbidden", "authz.forbidden"),
    ("access denied", "authz.forbidden"),
    ("authentication failed", "auth.failed"),
    ("invalid credentials", "auth.failed"),
    ("invalid token", "auth.failed"),
    ("login failed", "auth.failed"),
    ("approval", "governance.missing_approval"),
    ("change ticket", "governance.missing_approval"),
    ("audit log", "audit.trail_failure"),
    ("audit trail", "audit.trail_failure"),
    ("compliance", "compliance.breach"),
    ("hipaa", "compliance.breach"),
    ("sox", "compliance.breach"),
    ("gdpr", "compliance.breach"),
    ("exfiltrat", "dlp.exfiltration"),
    ("rate limit", "quota.rate_limited"),
    ("throttl", "quota.rate_limited"),
)


def _error_to_rule(exc: BaseException) -> str | None:
    """Map a caught exception to a G rule, or None if no rule applies.

    Resolution order:

    1. Exact class-name lookup in :data:`_ERROR_RULE_MAP`.
    2. Soft substring scan over the exception message (the
       framework's class name might be vendor-specific; the message
       usually isn't).
    3. None — the exception is recorded as an R incident but not
       promoted to a G violation. This is the right answer for
       generic errors (network timeouts, OOMs) that have no
       governance signal.
    """
    name = type(exc).__name__
    if name in _ERROR_RULE_MAP:
        return _ERROR_RULE_MAP[name]
    msg = (str(exc) or "").lower()
    if not msg:
        return None
    for needle, rule in _MESSAGE_RULE_HINTS:
        if needle in msg:
            return rule
    return None
