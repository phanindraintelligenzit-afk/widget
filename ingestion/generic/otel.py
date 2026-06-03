"""OTel span ingestion.

The other half of the universal fallback path: any agent that emits
OpenTelemetry spans can be scored without a bespoke adapter. We consume
a list of span dicts in the standard OTel shape and aggregate them per
agent over the observed period.

Recognised attributes (resource OR span-level):
    agent.id, agent.name                       — required-ish
    gen_ai.task                = true          — span counts as a task
    gen_ai.usage.output_tokens, input_tokens   — token totals
    policy.action              = true          — counts toward G denominator
    policy.violation           = true          — counts as a violation
    policy.violation.rule                      — rule name for violations
    incident.severity, incident.frequency      — feeds R
    incident.source
    quality.accuracy / consistency / hallucination_rate  — feeds Q
    validation.required, validation.validated  — feeds V
    cost.usd                                   — feeds C
    cost.systems_accessed

Anything else is ignored. This is the canonical mapping; teams that
want something more exotic should write a YAML mapping for the
GenericWebhookAdapter instead.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from contract import AgentObservation

from ..base import Adapter


def _attrs(span: dict) -> dict:
    """Merge resource attributes + span attributes — span wins."""
    out = dict(span.get("resource", {}) or {})
    out.update(span.get("attributes", {}) or {})
    return out


def _ts(span: dict, key: str) -> datetime | None:
    v = span.get(key)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # OTel uses nanoseconds since epoch.
        return datetime.fromtimestamp(v / 1e9, tz=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _status_ok(span: dict) -> bool:
    s = span.get("status")
    if isinstance(s, dict):
        return str(s.get("code", "OK")).upper() in ("OK", "UNSET")
    if isinstance(s, str):
        return s.upper() in ("OK", "UNSET")
    return True


class OTelAdapter(Adapter):
    name = "otel"

    def to_observations(self, payload: Any) -> list[AgentObservation]:
        spans: list[dict] = payload if isinstance(payload, list) else [payload]
        by_agent: dict[str, list[dict]] = defaultdict(list)
        for span in spans:
            a = _attrs(span)
            aid = a.get("agent.id", "unknown")
            by_agent[aid].append(span)
        return [self._aggregate(aid, ss) for aid, ss in by_agent.items()]

    def _aggregate(self, agent_id: str, spans: list[dict]) -> AgentObservation:
        starts = [t for t in (_ts(s, "start_time") or _ts(s, "start_time_unix_nano") for s in spans) if t]
        ends = [t for t in (_ts(s, "end_time") or _ts(s, "end_time_unix_nano") for s in spans) if t]
        # Fallback so AgentObservation validates even with no timestamps.
        now = datetime.now(timezone.utc)
        period_start = min(starts) if starts else now
        period_end = max(ends) if ends else now

        agent_name = "unknown"
        attempts = successful = failed = 0
        tasks_total = tasks_completed = tasks_failed = 0
        total_actions = 0
        violations: list[dict] = []
        incidents: list[dict] = []
        q_acc: list[float] = []
        q_con: list[float] = []
        q_hal: list[float] = []
        v_required = 0
        v_validated = 0
        cost_usd = 0.0
        tokens = 0
        systems = 0

        for s in spans:
            a = _attrs(s)
            agent_name = a.get("agent.name", agent_name)
            attempts += 1
            ok = _status_ok(s)
            if ok:
                successful += 1
            else:
                failed += 1

            if a.get("gen_ai.task"):
                tasks_total += 1
                if ok:
                    tasks_completed += 1
                else:
                    tasks_failed += 1

            if a.get("policy.action"):
                total_actions += 1
            if a.get("policy.violation"):
                violations.append({
                    "rule": a.get("policy.violation.rule", "unspecified"),
                    "when": (_ts(s, "end_time") or _ts(s, "end_time_unix_nano") or period_end).isoformat(),
                })

            if "incident.severity" in a:
                incidents.append({
                    "severity_weight": float(a["incident.severity"]),
                    "frequency": float(a.get("incident.frequency", 1)),
                    "source": a.get("incident.source", "otel"),
                })

            if "quality.accuracy" in a:
                q_acc.append(float(a["quality.accuracy"]))
            if "quality.consistency" in a:
                q_con.append(float(a["quality.consistency"]))
            if "quality.hallucination_rate" in a:
                q_hal.append(float(a["quality.hallucination_rate"]))

            if "validation.required" in a:
                v_required = max(v_required, int(a["validation.required"]))
            if "validation.validated" in a:
                v_validated = max(v_validated, int(a["validation.validated"]))

            cost_usd += float(a.get("cost.usd", 0))
            tokens += int(a.get("gen_ai.usage.output_tokens", 0))
            tokens += int(a.get("gen_ai.usage.input_tokens", 0))
            systems = max(systems, int(a.get("cost.systems_accessed", 0)))

        quality = None
        if q_acc or q_con or q_hal:
            def _avg(xs: list[float], default: float) -> float:
                return sum(xs) / len(xs) if xs else default
            quality = {
                "accuracy": _avg(q_acc, 0.0),
                "consistency": _avg(q_con, 0.0),
                "hallucination_rate": _avg(q_hal, 0.0),
            }

        per_output = (cost_usd / tasks_completed) if tasks_completed else 0.0

        return AgentObservation.model_validate({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "period_start": period_start,
            "period_end": period_end,
            "tasks": {
                "assigned": tasks_total or attempts,
                "completed": tasks_completed or successful,
                "failed": tasks_failed or failed,
            },
            "executions": {"attempts": attempts, "successful": successful},
            "policy": {"total_actions": total_actions, "violations": violations},
            "incidents": incidents,
            "quality": quality,
            "validation": {
                "required_components": v_required,
                "validated_components": v_validated,
                "audit_ready": v_required > 0 and v_validated >= v_required,
            },
            "cost": {
                "ai_cost_per_output": per_output,
                "tokens": tokens,
                "cloud_cost": cost_usd,
                "systems_accessed": systems,
            },
            "source": "otel",
        })
