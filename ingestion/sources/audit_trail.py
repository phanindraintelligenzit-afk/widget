"""Generic Audit Trail → G (governance).

Accepts a generic list of policy violations and maps them directly
to the agent's Governance (G) dimension. Useful as a central catch-all
for ad-hoc policy breaches reported by internal scripts or reviews.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import PartialObservation, Policy, PolicyViolation

from .base import SourceAdapter


class AuditTrailAdapter(SourceAdapter):
    name = "audit_trail"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "agents": [
                {
                  "agent_id": "...",
                  "violations": [
                    {"rule": "unauthorized_data_access", "at": "..."}
                  ]
                }
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        out: list[PartialObservation] = []
        
        for a in payload.get("agents", []):
            policy = None
            if "violations" in a:
                violations_data = a["violations"]
                if violations_data:
                    policy = Policy(
                        total_actions=100,  # Arbitrary denominator for policy events if not tracking total actions
                        violations=[
                            PolicyViolation(
                                rule=v["rule"],
                                when=_parse_dt(v["at"])
                            )
                            for v in violations_data
                        ]
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
