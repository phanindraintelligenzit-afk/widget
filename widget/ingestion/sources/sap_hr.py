"""SAP HR telemetry → Governance (G) dimension.

Parses HR compliance alerts and maps them to policy violations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import PartialObservation, Policy, PolicyViolation

from .base import SourceAdapter


class SapHrAdapter(SourceAdapter):
    name = "sap_hr"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        
        out: list[PartialObservation] = []
        for alert in payload.get("hr_alerts", []):
            aid = alert.get("agent_id")
            if not aid:
                continue
                
            violations = [
                PolicyViolation(rule=v["rule"], when=_parse_dt(v["timestamp"]))
                for v in alert.get("violations", [])
            ]
            
            policy = Policy(
                total_actions=int(alert.get("total_scanned_actions", 0)),
                violations=violations,
            )
            
            out.append(PartialObservation(
                agent_id=aid,
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
