"""Jira incidents → R (reliability dimension).

Jira's priority taxonomy is Highest/High/Medium/Low/Lowest. Mapped to
severity_weight 1.0 / 0.75 / 0.5 / 0.3 / 0.15. The agent is tagged
via a custom field on each issue (`customfield_agent_id`).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from contract import Incident, PartialObservation

from .base import SourceAdapter


_PRIORITY = {
    "Highest": 1.0, "High": 0.75, "Medium": 0.5, "Low": 0.3, "Lowest": 0.15,
}


class JiraAdapter(SourceAdapter):
    name = "jira"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "issues": [
                {
                  "key": "INC-101",
                  "fields": {
                    "customfield_agent_id": "...",
                    "priority": {"name": "High"},
                    "created": "..."
                  }
                }, ...
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        by_agent: dict[str, list[Incident]] = defaultdict(list)
        for issue in payload.get("issues", []):
            f = issue.get("fields", {}) or {}
            aid = f.get("customfield_agent_id")
            if not aid:
                continue
            priority_name = (f.get("priority") or {}).get("name", "Medium")
            by_agent[aid].append(Incident(
                severity_weight=_PRIORITY.get(priority_name, 0.5),
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
