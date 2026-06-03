"""AWS Cost Explorer → C (cost-efficiency dimension).

Real wire shape: a GetCostAndUsage response with GroupBy=TAG
(`Key=AGENT_ID`) — each group's metric is the dollars spent under that
agent's tag over the period. We divide by output_count (caller supplies
it; commonly from CloudWatch or the agent's own metrics) to get
ai_cost_per_output.

Mock-first: pass in the JSON shape directly (see
fixtures/aws_cost_response.json). The wire fetch (boto3) is intentionally
not wired up — the demo never blocks on credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import Cost, PartialObservation

from .base import SourceAdapter


class AwsCostAdapter(SourceAdapter):
    name = "aws_cost"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": "2026-06-01T00:00:00Z",
              "period_end":   "2026-06-02T00:00:00Z",
              "agents": [
                {
                  "agent_id": "...",
                  "agent_name": "...",         # optional
                  "spend_usd": 12.40,
                  "output_count": 88,           # tasks/outputs in the window
                  "tokens": 540000,             # optional
                  "cloud_cost_usd": 12.40,      # optional, defaults to spend_usd
                  "systems_accessed": 4         # optional
                }, ...
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        out: list[PartialObservation] = []
        for a in payload.get("agents", []):
            output_count = max(int(a.get("output_count", 0)), 0)
            spend = float(a.get("spend_usd", 0.0))
            ai_cost_per_output = (spend / output_count) if output_count > 0 else 0.0
            cost = Cost(
                ai_cost_per_output=ai_cost_per_output,
                tokens=int(a.get("tokens", 0)),
                cloud_cost=float(a.get("cloud_cost_usd", spend)),
                systems_accessed=int(a.get("systems_accessed", 0)),
            )
            out.append(PartialObservation(
                agent_id=a["agent_id"],
                agent_name=a.get("agent_name"),
                period_start=start,
                period_end=end,
                source=self.name,
                cost=cost,
            ))
        return out


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
