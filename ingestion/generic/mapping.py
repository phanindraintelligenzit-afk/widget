"""Declarative field mapping: arbitrary JSON → canonical AgentObservation.

A FieldMapping is YAML. Three constructs:

* string         — a JSONPath-lite expression resolved against the root
* dict           — nested mapping (recurses into observation sub-fields)
* dict + _each   — iterate a list at _each, apply the rest per item

Optional groups (e.g. quality) can declare `_optional: true` so that a
group of all-null resolutions collapses to None — preserving the
engine's "needs conversational input" signal instead of zeroing the
metric.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from contract import AgentObservation

from .jsonpath import resolve

# Canonical top-level observation fields we will populate.
_OBS_FIELDS = (
    "agent_id",
    "agent_name",
    "period_start",
    "period_end",
    "tasks",
    "executions",
    "policy",
    "incidents",
    "quality",
    "validation",
    "cost",
    "source",
)


def _apply(spec: Any, ctx: Any) -> Any:
    if spec is None:
        return None
    if isinstance(spec, str):
        return resolve(spec, ctx)
    if isinstance(spec, list):
        return [_apply(s, ctx) for s in spec]
    if isinstance(spec, dict):
        optional = bool(spec.get("_optional", False))
        each_path = spec.get("_each")
        sub = {k: v for k, v in spec.items() if k not in ("_optional", "_each")}

        if each_path is not None:
            items = resolve(each_path, ctx) or []
            return [_apply(sub, item) for item in items if item is not None]

        result = {k: _apply(v, ctx) for k, v in sub.items()}
        if optional and all(v is None for v in result.values()):
            return None
        return result
    # Literal (int, float, bool) — pass through.
    return spec


class FieldMapping(BaseModel):
    """YAML-driven mapping. Build with `from_yaml()` or `from_string()`."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    spec: dict

    @classmethod
    def from_yaml(cls, path: str | Path) -> "FieldMapping":
        return cls(spec=yaml.safe_load(Path(path).read_text()) or {})

    @classmethod
    def from_string(cls, text: str) -> "FieldMapping":
        return cls(spec=yaml.safe_load(text) or {})

    def apply(self, payload: Any) -> AgentObservation:
        # Constants first; mapped fields can override.
        raw: dict[str, Any] = dict(self.spec.get("constants", {}) or {})
        for field in _OBS_FIELDS:
            if field in self.spec:
                raw[field] = _apply(self.spec[field], payload)
        return AgentObservation.model_validate(raw)
