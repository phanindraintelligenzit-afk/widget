"""MLflow model tracking → C (cost) + V (validation).

MLflow tracks agent runs, inputs, costs, and audit-readiness checklists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from contract import PartialObservation
from contract.models import Cost, Validation

from .base import SourceAdapter


class MlflowAdapter(SourceAdapter):
    name = "mlflow"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "agents": [
                {
                  "agent_id": "...",
                  "cost": {                 # optional
                    "input_tokens": 120000,
                    "output_tokens": 40000,
                    "model_cost": 1.24,
                    "number_of_llm_calls": 5,
                    "Human_cost": 50.0
                  },
                  "validation": {           # optional
                    "required_components": 2,
                    "validated_components": 2,
                    "audit_ready": true
                  }
                }
              ]
            }
        """
        if "period_start" not in payload or "period_end" not in payload:
            raise HTTPException(status_code=422, detail="Missing period_start or period_end")
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
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
            out.append(PartialObservation(
                agent_id=a["agent_id"],
                agent_name=a.get("agent_name"),
                period_start=start,
                period_end=end,
                source=self.name,
                cost=cost,
                validation=validation,
            ))
        return out


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
