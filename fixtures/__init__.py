"""Synthetic fixtures for mock-first development. Clearly labelled."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contract import AgentObservation

_DIR = Path(__file__).parent


def load(name: str) -> AgentObservation:
    """Load a canonical observation fixture by short name."""
    path = _DIR / f"obs_{name}.json"
    data = json.loads(path.read_text())
    data.pop("_label", None)
    return AgentObservation.model_validate(data)


def all_observations() -> dict[str, AgentObservation]:
    out: dict[str, AgentObservation] = {}
    for f in sorted(_DIR.glob("obs_*.json")):
        name = f.stem.removeprefix("obs_")
        out[name] = load(name)
    return out


def load_raw(name: str) -> Any:
    """Load a raw, non-canonical payload fixture (input to an adapter)."""
    path = _DIR / f"raw_{name}.json"
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data.pop("_label", None)
    return data


def mapping_path(name: str) -> Path:
    """Path to a YAML mapping fixture."""
    return _DIR / f"mapping_{name}.yaml"


def load_otel_spans(name: str = "spans") -> list[dict]:
    """Load OTel span fixtures."""
    return json.loads((_DIR / f"otel_{name}.json").read_text())
