"""AWS Bedrock telemetry → C (cost dimension).

Parses aggregated token and cost usage per agent from AWS Bedrock metrics.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from contract import Cost, PartialObservation

from .base import SourceAdapter


class BedrockAdapter(SourceAdapter):
    name = "bedrock"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "bedrock_usage": [
                {
                  "agent_id": "...",
                  "model": "...",
                  "input_tokens": 15000,
                  "output_tokens": 4000,
                  "estimated_cost_usd": 0.06
                }, ...
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        
        # Accumulate usage per agent (in case payload has multiple rows per agent)
        agent_costs: dict[str, Cost] = {}
        
        for usage in payload.get("bedrock_usage", []):
            aid = usage.get("agent_id")
            if not aid:
                continue
                
            in_tokens = int(usage.get("input_tokens", 0))
            out_tokens = int(usage.get("output_tokens", 0))
            usd_cost = float(usage.get("estimated_cost_usd", 0.0))
            
            if aid not in agent_costs:
                agent_costs[aid] = Cost(
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    model_cost=usd_cost
                )
            else:
                agent_costs[aid].input_tokens += in_tokens
                agent_costs[aid].output_tokens += out_tokens
                agent_costs[aid].model_cost += usd_cost
                
        return [
            PartialObservation(
                agent_id=aid,
                period_start=start,
                period_end=end,
                source=self.name,
                cost=cost,
            )
            for aid, cost in agent_costs.items()
        ]


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
