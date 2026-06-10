"""Generic Audit Trail → G (governance).

Accepts a generic list of policy violations and maps them directly
to the agent's Governance (G) dimension. Useful as a central catch-all
for ad-hoc policy breaches reported by internal scripts or reviews.

The ``total_actions`` denominator is *required* in the payload — the
adapter refuses to invent a number for it (a hard-coded
``total_actions=100`` would silently produce a G of 0.95 for any agent
that leaked 5 secrets, which is the wrong answer for a
governance-critical dimension). If the upstream audit-trail system
cannot provide a denominator, it must be recorded in the payload
alongside the violations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from contract import PartialObservation, Policy, PolicyViolation

from .base import SourceAdapter


# Minimum acceptable denominator for G to be a meaningful ratio.
# Below this, the engine's vacuous-default of 1.0 is the safer answer
# (and the gate stays quiet) — see ``engine.metrics.compute_G``.
_MIN_TOTAL_ACTIONS = 1


class AuditTrailAdapter(SourceAdapter):
    name = "audit_trail"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "agents": [
                {
                  "agent_id": "...",
                  "total_actions": 200,    # REQUIRED when violations present
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
                    # ``total_actions`` is required when violations
                    # are reported — without it G is meaningless (the
                    # engine's vacuous-default of 1.0 would hide a
                    # real breach). Reject the payload loudly so the
                    # upstream caller knows to fix their emitter.
                    if "total_actions" not in a:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                f"audit_trail: agent '{a.get('agent_id')}' "
                                f"reported {len(violations_data)} violation(s) "
                                f"but no 'total_actions' denominator. "
                                f"Add 'total_actions' to the audit-trail payload."
                            ),
                        )
                    total = int(a["total_actions"])
                    if total < _MIN_TOTAL_ACTIONS:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                f"audit_trail: agent '{a.get('agent_id')}' "
                                f"reported total_actions={total}; must be "
                                f">= {_MIN_TOTAL_ACTIONS} for a meaningful G."
                            ),
                        )
                    policy = Policy(
                        total_actions=total,
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
