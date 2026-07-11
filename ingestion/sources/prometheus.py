"""Prometheus Metrics → C (cost) + V (validation) + E (executions).

Parses scraped or pushed metrics from Prometheus.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import PartialObservation
from contract.models import Cost, Validation, Executions

from .base import SourceAdapter


class PrometheusAdapter(SourceAdapter):
    name = "prometheus"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape:

            {
              "period_start": ..., "period_end": ...,
              "agents": [
                {
                  "agent_id": "...",
                  "cost": {
                    "input_tokens": 120000,
                    "output_tokens": 40000,
                    "model_cost": 1.24,
                    "number_of_llm_calls": 5,
                    "Human_cost": 50.0
                  },
                  "validation": {
                    "required_components": 2,
                    "validated_components": 2,
                    "audit_ready": true
                  },
                  "executions": {
                    "attempts": 10,
                    "successful": 9
                  }
                }
              ]
            }
        """
        start = _parse_dt(payload.get("period_start", datetime.now(timezone.utc)))
        end = _parse_dt(payload.get("period_end", datetime.now(timezone.utc)))
        out: list[PartialObservation] = []
        
        for a in payload.get("agents", []):
            cost = None
            if "cost" in a and a["cost"] is not None:
                c = a["cost"]
                cost = Cost(
                    input_tokens=int(c.get("input_tokens", 0)),
                    output_tokens=int(c.get("output_tokens", 0)),
                    model_cost=float(c.get("model_cost", 0.0)),
                    number_of_llm_calls=int(c.get("number_of_llm_calls", 0)),
                    Human_cost=float(c.get("Human_cost", 0.0)),
                )
            validation = None
            if "validation" in a and a["validation"] is not None:
                v = a["validation"]
                validation = Validation(
                    required_components=int(v.get("required_components", 0)),
                    validated_components=int(v.get("validated_components", 0)),
                    audit_ready=bool(v.get("audit_ready", False)),
                )
            executions = None
            if "executions" in a and a["executions"] is not None:
                ex = a["executions"]
                executions = Executions(
                    attempts=int(ex.get("attempts", 0)),
                    successful=int(ex.get("successful", 0)),
                )
            
            out.append(PartialObservation(
                agent_id=a["agent_id"],
                agent_name=a.get("agent_name"),
                period_start=start,
                period_end=end,
                source=self.name,
                cost=cost,
                validation=validation,
                executions=executions,
            ))
            
        return out


def _parse_dt(s: Any) -> datetime:
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
