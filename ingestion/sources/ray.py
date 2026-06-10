"""Ray observability → E (executions) + R (incidents) + G (policy).

Ray runtime metrics capture:
    * task retries   → Executions (lowers E)
    * actor crashes  → Incidents (lowers R)
    * quota breaches → Policy violations (lowers G)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import Executions, Incident, PartialObservation, Policy, PolicyViolation

from .base import SourceAdapter


class RayAdapter(SourceAdapter):
    name = "ray"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "agents": [
                {
                  "agent_id": "...",
                  "successful_tasks": 100,
                  "task_retries": 5,
                  "actor_crashes": 1,
                  "quota_breaches": [
                    {"resource": "memory.oom", "at": "..."}
                  ]
                }
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        out: list[PartialObservation] = []
        
        for a in payload.get("agents", []):
            executions = None
            if "successful_tasks" in a or "task_retries" in a:
                successful = int(a.get("successful_tasks", 0))
                retries = int(a.get("task_retries", 0))
                executions = Executions(
                    successful=successful,
                    attempts=successful + retries
                )
            
            incidents = None
            crashes = int(a.get("actor_crashes", 0))
            if crashes > 0:
                incidents = [
                    Incident(
                        severity_weight=0.8,  # High severity
                        frequency=1.0,        # 1 incident per crash
                        source="ray.actor_crash"
                    )
                    for _ in range(crashes)
                ]
            
            policy = None
            if "quota_breaches" in a:
                breaches = a["quota_breaches"]
                if breaches:
                    policy = Policy(
                        total_actions=100,  # Arbitrary denominator for quota events if not given
                        violations=[
                            PolicyViolation(
                                rule=f"quota.{b['resource']}",
                                when=_parse_dt(b["at"])
                            )
                            for b in breaches
                        ]
                    )
            
            out.append(PartialObservation(
                agent_id=a["agent_id"],
                agent_name=a.get("agent_name"),
                period_start=start,
                period_end=end,
                source=self.name,
                executions=executions,
                incidents=incidents if incidents else [],
                policy=policy,
            ))
            
        return out


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
