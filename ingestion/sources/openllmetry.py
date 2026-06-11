"""OpenLLMetry Webhooks → Executions (E) dimension.

Parses execution telemetry from OpenLLMetry.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import Executions, PartialObservation

from .base import SourceAdapter


class OpenLLMetryAdapter(SourceAdapter):
    name = "openllmetry"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        start = _parse_dt(payload.get("period_start", datetime.now(timezone.utc)))
        end = _parse_dt(payload.get("period_end", datetime.now(timezone.utc)))
        
        out: list[PartialObservation] = []
        for exec_data in payload.get("runs", payload.get("traces", [])):
            aid = exec_data.get("agent_id") or payload.get("agent_id")
            if not aid:
                continue
                
            attempts = int(exec_data.get("tool_attempts", exec_data.get("attempts", 0)))
            successful = int(exec_data.get("tool_successes", exec_data.get("successful", 0)))
            if attempts == 0 and successful > 0:
                attempts = successful
            if attempts == 0:
                continue
            
            out.append(PartialObservation(
                agent_id=aid,
                period_start=start,
                period_end=end,
                source=self.name,
                executions=Executions(successful=successful, attempts=attempts),
            ))
            
        return out

def _parse_dt(s: Any) -> datetime:
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
