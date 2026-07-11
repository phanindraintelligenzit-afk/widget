"""Puvi noise governance → G (policy violations dimension).

Puvi is a prompt/output safety scanner. Each alert flags one action
that breached a policy (PII leakage, prompt injection, jailbreak, etc).
The total_actions count comes from the policy_evaluations field —
"how many actions did we evaluate, of which how many tripped a rule."
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import PartialObservation, Policy, PolicyViolation

from .base import SourceAdapter


class PuviNoiseAdapter(SourceAdapter):
    name = "puvi_noise"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "agents": [
                {
                  "agent_id": "...",
                  "policy_evaluations": 200,
                  "alerts": [
                    {"rule": "pii.pan_card", "timestamp": "..."},
                    ...
                  ]
                }
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        out: list[PartialObservation] = []
        for a in payload.get("agents", []):
            violations = [
                PolicyViolation(rule=alert["rule"], when=_parse_dt(alert["timestamp"]))
                for alert in a.get("alerts", [])
            ]
            policy = Policy(
                total_actions=int(a.get("policy_evaluations", 0)),
                violations=violations,
            )
            out.append(PartialObservation(
                agent_id=a["agent_id"],
                agent_name=a.get("agent_name"),
                period_start=start,
                period_end=end,
                source=self.name,
                policy=policy,
            ))
        return out


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
