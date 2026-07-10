"""BMC Remedy incidents → R (risk dimension).

Maps BMC Remedy priorities to the engine's severity_weight:
Critical -> 1.0
High     -> 0.75
Medium   -> 0.5
Low      -> 0.3
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from contract import Incident, PartialObservation

from .base import SourceAdapter


class BmcAdapter(SourceAdapter):
    name = "bmc"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "incidents": [
                {
                  "incident_id": "INC-8882",
                  "agent_id": "chandra-finops",
                  "priority": "Critical",
                  "reported_date": "..."
                }, ...
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        by_agent: dict[str, list[Incident]] = defaultdict(list)
        
        for inc in payload.get("incidents", []):
            aid = inc.get("agent_id")
            if not aid:
                continue
                
            priority_str = str(inc.get("priority", "Medium")).lower()
            
            if "critical" in priority_str:
                severity = 1.0
            elif "high" in priority_str:
                severity = 0.75
            elif "medium" in priority_str:
                severity = 0.5
            elif "low" in priority_str:
                severity = 0.3
            else:
                # Default for unknown priorities
                severity = 0.5
                
            by_agent[aid].append(Incident(
                severity_weight=severity,
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
