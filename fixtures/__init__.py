"""Synthetic observations for mock-first development. Clearly labelled."""
from __future__ import annotations

import json
from pathlib import Path

from contract import AgentObservation

_DIR = Path(__file__).parent


def load(name: str) -> AgentObservation:
    """Load a fixture by short name (e.g. 'strong', 'baseline', 'unsafe')."""
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
