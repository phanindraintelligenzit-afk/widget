"""Langfuse Webhooks → Executions (E) dimension.

Parses execution telemetry from Langfuse.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import Executions, PartialObservation

from .base import SourceAdapter


class LangfuseAdapter(SourceAdapter):
    name = "langfuse"

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
            
            cost = None
            if "cost" in exec_data and exec_data["cost"] is not None:
                c = exec_data["cost"]
                from contract.models import Cost
                cost = Cost(
                    input_tokens=int(c.get("input_tokens", 0)),
                    output_tokens=int(c.get("output_tokens", 0)),
                    model_cost=float(c.get("model_cost", 0.0)),
                    number_of_llm_calls=int(c.get("number_of_llm_calls", 0)),
                    Human_cost=float(c.get("Human_cost", 0.0)),
                )
            validation = None
            if "validation" in exec_data and exec_data["validation"] is not None:
                v = exec_data["validation"]
                from contract.models import Validation
                validation = Validation(
                    required_components=int(v.get("required_components", 0)),
                    validated_components=int(v.get("validated_components", 0)),
                    audit_ready=bool(v.get("audit_ready", False)),
                )
            
            out.append(PartialObservation(
                agent_id=aid,
                period_start=start,
                period_end=end,
                source=self.name,
                executions=Executions(successful=successful, attempts=attempts),
                cost=cost,
                validation=validation,
            ))
            
        return out

def _parse_dt(s: Any) -> datetime:
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
