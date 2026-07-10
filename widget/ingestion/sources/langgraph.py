"""LangGraph Cloud Webhooks → Executions (E) and Productivity (P) dimensions.

Parses success/failure counts from external LangGraph deployments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import Executions, PartialObservation, TaskStats

from .base import SourceAdapter


class LangGraphAdapter(SourceAdapter):
    name = "langgraph"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        
        out: list[PartialObservation] = []
        for exec_data in payload.get("executions", []):
            aid = exec_data.get("agent_id")
            if not aid:
                continue
                
            successful = int(exec_data.get("successful_runs", 0))
            failed = int(exec_data.get("failed_runs", 0))
            total = successful + failed
            
            out.append(PartialObservation(
                agent_id=aid,
                period_start=start,
                period_end=end,
                source=self.name,
                executions=Executions(successful=successful, attempts=total),
                tasks=TaskStats(assigned=total, completed=successful, failed=failed),  # Productivity
            ))
            
        return out


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
