"""Ray observability → E (executions) + R (incidents) + G (policy).

Ray runtime metrics capture:
    * task retries   → Executions (lowers E)
    * actor crashes  → Incidents (lowers R)
    * quota breaches → Policy violations (lowers G)

The G denominator is derived from Ray's own counters:
``successful_tasks + task_retries + actor_crashes`` — the total
number of policy-gated actions Ray evaluated in the period. When the
payload doesn't include those fields but does include
``quota_breaches``, the adapter accepts an explicit ``total_actions``
from the payload, or fails loudly with a 422 rather than silently
manufacturing a denominator.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from contract import Executions, Incident, PartialObservation, Policy, PolicyViolation

from .base import SourceAdapter


# Minimum acceptable denominator for G to be a meaningful ratio.
# Below this, the engine's vacuous-default of 1.0 is the safer answer
# (and the gate stays quiet) — see ``engine.metrics.compute_G``.
_MIN_TOTAL_ACTIONS = 1


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
                  ],
                  "total_actions": 106   # OPTIONAL — overrides derived
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
                    # Derive the denominator from Ray's own counters
                    # when possible. Fall back to an explicit
                    # ``total_actions`` field if the caller has a
                    # better number. Reject (rather than guess) if
                    # neither is present — a wrong denominator for G
                    # is worse than no G.
                    successful = int(a.get("successful_tasks", 0))
                    retries = int(a.get("task_retries", 0))
                    if "total_actions" in a:
                        total = int(a["total_actions"])
                    else:
                        total = successful + retries + crashes
                    if total < _MIN_TOTAL_ACTIONS:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                f"ray: agent '{a.get('agent_id')}' "
                                f"reported {len(breaches)} quota_breach(es) "
                                f"but the derived total_actions is {total} "
                                f"(successful_tasks={successful}, "
                                f"task_retries={retries}, "
                                f"actor_crashes={crashes}). Provide a "
                                f"'total_actions' field in the payload."
                            ),
                        )
                    policy = Policy(
                        total_actions=total,
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
