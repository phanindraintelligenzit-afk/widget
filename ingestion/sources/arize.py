"""Arize model monitoring → G (governance) + Q (quality).

Arize emits two kinds of signals we care about:
    * monitor breaches  → policy violations (drives G)
    * quality scores    → accuracy / consistency / hallucination_rate (drives Q)

Either or both may be present per agent. Missing dimensions stay None.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contract import PartialObservation, Policy, PolicyViolation, Quality

from .base import SourceAdapter


class ArizeAdapter(SourceAdapter):
    name = "arize"

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        """Expected payload shape::

            {
              "period_start": ..., "period_end": ...,
              "agents": [
                {
                  "agent_id": "...",
                  "model_inferences": 1200,
                  "monitor_breaches": [
                    {"monitor": "drift.embedding_l2", "at": "..."},
                    ...
                  ],
                  "quality": {                 # optional
                    "accuracy": 0.93,
                    "consistency": 0.91,
                    "hallucination_rate": 0.04
                  }
                }
              ]
            }
        """
        start = _parse_dt(payload["period_start"])
        end = _parse_dt(payload["period_end"])
        out: list[PartialObservation] = []
        for a in payload.get("agents", []):
            policy = None
            if "monitor_breaches" in a or "model_inferences" in a:
                breaches = a.get("monitor_breaches", [])
                policy = Policy(
                    total_actions=int(a.get("model_inferences", len(breaches))),
                    violations=[
                        PolicyViolation(rule=b["monitor"], when=_parse_dt(b["at"]))
                        for b in breaches
                    ],
                )
            quality = None
            if "quality" in a and a["quality"] is not None:
                q = a["quality"]
                quality = Quality(
                    accuracy=float(q["accuracy"]),
                    consistency=float(q["consistency"]),
                    hallucination_rate=float(q["hallucination_rate"]),
                )
            out.append(PartialObservation(
                agent_id=a["agent_id"],
                agent_name=a.get("agent_name"),
                period_start=start,
                period_end=end,
                source=self.name,
                policy=policy,
                quality=quality,
            ))
        return out


def _parse_dt(s: str) -> datetime:
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
