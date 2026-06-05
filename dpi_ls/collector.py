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
from typing import Any, Optional

from .policy import scan_policy_violations

# Cap how many full outputs we keep for the LLM evaluator. The last N are
# the most representative of how the run actually ended, and feeding the
# full conversation into three LLM calls is wasteful.
_MAX_OUTPUTS_FOR_Q = 6

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

    # P — agent-level run counter. Each time the agent completes a full
    # invocation (Runner.run returns, Crew kicks off, etc.) this is +1.
    # It is separate from LLM-level attempts so P measures agent runs,
    # not individual LLM calls inside one run.
    agent_runs_completed: int = 0
    agent_runs_failed: int = 0

    # G — governance. Each violation is a (rule, when) tuple.
    violations: list[dict] = field(default_factory=list)

    # R — risk. Each incident is a (severity_weight, frequency, source).
    incidents: list[dict] = field(default_factory=list)

    # C — cost. Tokens in/out summed across calls; cloud cost approximated
    # by token price × tokens; ``systems_accessed`` is a de-duped set of
    # base URLs the agent called against.
    tokens_in: int = 0
    tokens_out: int = 0
    cloud_cost: float = 0.0
    _systems_accessed: set[str] = field(default_factory=set)

    # V — validation. We treat any output that looks like a structured
    # payload (valid JSON, has "answer"/"result" key, or matches the
    # required-schema spec) as validated. The collector does best-effort
    # heuristics, not a real schema validator.
    validated_outputs: int = 0
    total_outputs: int = 0

    # Q — quality. Set by the LangGraph evaluator after the run finishes.
    quality: Optional[dict] = None  # {accuracy, consistency, hallucination_rate}

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
    ) -> None:
        """One LLM call completed. Records tokens/cost/output for Q."""
        with self._lock:
            self.attempts += 1
            if ok:
                self.successful += 1
            else:
                self.failed += 1
            self.tokens_in += int(tokens_in or 0)
            self.tokens_out += int(tokens_out or 0)
            self.cloud_cost += float(cost or 0.0)
        if output:
            self._capture_output(output, system=system)

    def record_tool_call(self, *, ok: bool = True) -> None:
        with self._lock:
            self.attempts += 1
            if ok:
                self.successful += 1
            else:
                self.failed += 1

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

    # ---- accessors used by finalize() ---------------------------------

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
        # G: deterministic policy scan over the output text.
        for rule in scan_policy_violations(output):
            self.violations.append(
                {"rule": rule, "when": _utcnow().isoformat()}
            )
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
        # If we have no cloud cost at all, estimate from token counts.
        tokens_total = self.tokens_in + self.tokens_out
        estimated_cost = self.cloud_cost
        if estimated_cost == 0.0 and tokens_total > 0:
            # Conservative blended estimate: $0.001 per 1k tokens
            estimated_cost = tokens_total * 0.000001
        ai_cost_per_output = (
            estimated_cost / completed_runs if completed_runs > 0
            else (estimated_cost if estimated_cost > 0 else 0.0)
        )

        # V — validation: fraction of captured outputs that look structured.
        # Use total_outputs as the required count; if zero but we had
        # attempts, treat attempts as required so V isn't vacuously 1.0.
        required = self.total_outputs
        if required == 0 and self.attempts > 0:
            required = self.attempts
        validated = self.validated_outputs

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
            },
            "policy": {
                "total_actions": max(self.attempts, 1),
                "violations": self.violations,
            },
            "incidents": self.incidents,
            "validation": {
                "required_components": required,
                "validated_components": validated,
                "audit_ready": required > 0 and validated >= required,
            },
            "cost": {
                "ai_cost_per_output": ai_cost_per_output,
                "tokens": tokens_total,
                "cloud_cost": estimated_cost,
                "systems_accessed": len(self._systems_accessed),
            },
            "source": f"dpi_ls:{self.framework}",
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

# Some error names map cleanly to a policy rule. Keeping this list short —
# anything else is recorded as an incident but not a violation.
_ERROR_RULE_MAP: dict[str, str] = {
    "PermissionDeniedError": "auth.permission_denied",
    "AuthenticationError": "auth.failed",
    "RateLimitError": "quota.rate_limited",
    "PiiLeakageError": "pii.leakage",
}


def _error_to_rule(exc: BaseException) -> str | None:
    name = type(exc).__name__
    if name in _ERROR_RULE_MAP:
        return _ERROR_RULE_MAP[name]
    # Soft check for "pii" in the message — many PII tools raise
    # framework-specific subclasses.
    msg = (str(exc) or "").lower()
    if "pii" in msg or "redact" in msg:
        return "pii.leakage"
    return None
