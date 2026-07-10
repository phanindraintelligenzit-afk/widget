"""AWS Cost Explorer → C (cost-efficiency dimension).

Real wire shape: a GetCostAndUsage response with GroupBy=TAG
(`Key=AGENT_ID`) — each group's metric is the dollars spent under that
agent's tag over the period. We forward ``spend_usd`` as ``model_cost``
so the engine can derive the per-output figure it actually needs for
the C formula (``model_cost / tasks.completed``).

If the caller also supplies ``output_count`` (common — the same
CloudWatch metric the AWS Cost adapter typically reads next to
Cost Explorer), we forward it as a ``tasks`` block on the partial.
That way ``tasks.completed`` is the right denominator and the per-
output math comes out the same as the pre-refactor behavior. Without
``output_count`` the adapter stays strictly cost-only; the engine then
treats the cost total as a single-output figure (denominator = 1),
which is a safe-but-pessimistic fallback.

Mock-first: pass in the JSON shape directly (see
fixtures/aws_cost_response.json). The wire fetch (boto3) is intentionally
not wired up — the demo never blocks on credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import Cost, PartialObservation, TaskStats

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
                  "agent_id":     "...",
                  "agent_name":   "...",        # optional
                  "spend_usd":    12.40,
                  "output_count": 88,           # optional
                  "input_tokens": 200000,       # optional
                  "output_tokens":100000,       # optional
                  "tokens":       300000        # optional legacy rollup
                }, ...
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        out: list[PartialObservation] = []
        for a in payload.get("agents", []):
            spend = float(a.get("spend_usd", 0.0))
            output_count = max(int(a.get("output_count", 0)), 0)
            # Accept both an in/out split (preferred) and the legacy
            # combined "tokens" rollup for backwards compat with
            # existing fixtures.
            in_t = int(a.get("input_tokens", 0))
            out_t = int(a.get("output_tokens", 0))
            if in_t == 0 and out_t == 0:
                legacy = int(a.get("tokens", 0))
                in_t = legacy // 2
                out_t = legacy - in_t
            cost = Cost(
                input_tokens=in_t,
                output_tokens=out_t,
                model_cost=spend,
            )
            # Forward ``output_count`` as a tasks block so the engine's
            # ``model_cost / tasks.completed`` division gives the same
            # per-output figure the old contract carried directly.
            tasks = (
                TaskStats(assigned=output_count, completed=output_count, failed=0)
                if output_count
                else None
            )
            out.append(PartialObservation(
                agent_id=a["agent_id"],
                agent_name=a.get("agent_name"),
                period_start=start,
                period_end=end,
                source=self.name,
                cost=cost,
                tasks=tasks,
            ))
        return out


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
