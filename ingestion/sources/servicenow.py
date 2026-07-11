"""ServiceNow incident tickets → R (risk dimension).

ServiceNow uses an `impact` field (1=high, 3=low). We map that to the
severity_weight the engine expects (1.0 / 0.6 / 0.3 for impact 1/2/3,
linearly otherwise). One ticket = one incident with frequency 1.

The agent association is on the ticket itself (custom field
`u_agent_id`). Tickets without that field are dropped — the engine
never invents an agent.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from contract import Incident, PartialObservation

from .base import SourceAdapter


def _impact_to_weight(impact: int) -> float:
    return {1: 1.0, 2: 0.6, 3: 0.3}.get(impact, max(0.0, min(1.0, (4 - impact) / 3)))


class ServiceNowAdapter(SourceAdapter):
    name = "servicenow"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "tickets": [
                {"u_agent_id": "...", "impact": 1, "opened_at": "..."},
                ...
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        by_agent: dict[str, list[Incident]] = defaultdict(list)
        for t in payload.get("tickets", []):
            aid = t.get("u_agent_id")
            if not aid:
                continue
            by_agent[aid].append(Incident(
                severity_weight=_impact_to_weight(int(t.get("impact", 3))),
                frequency=1.0,
                source=self.name,
            ))
        return [
            PartialObservation(
                agent_id=aid,
                period_start=start,
                period_end=end,
                source=self.name,
                incidents=incidents,
            )
            for aid, incidents in by_agent.items()
        ]


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
