"""Build and POST the final AgentObservation to the dashboard.

Single entry point: ``post_observation(collector, base_url)`` takes a
populated ``SignalCollector`` and pushes the canonical observation to
``/ingest``. The server is the existing FastAPI app (started in
``server.py``); we don't bypass it with a direct DB write so the
history/board/score rows are populated by the same path a manual
ingest would use.

Failures here are non-fatal — the agent run itself is the user's
product, the dashboard is the demo surface. We log the failure and
move on.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

from .collector import SignalCollector

_log = logging.getLogger("dpi_ls.poster")

_DEFAULT_TIMEOUT_S = 10.0


def post_observation(
    collector: SignalCollector,
    base_url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> Optional[dict[str, Any]]:
    """POST the collector's observation to ``{base_url}/ingest``.

    Passes ``human_baseline`` as a query param when set so the API updates
    the agent's DB baseline before scoring — this is what makes P meaningful
    for single-run agents (baseline=1) vs batch agents (baseline=100).

    Returns the rating dict on success, ``None`` on failure (already
    logged). Never raises.
    """
    obs = collector.to_observation()
    url = base_url.rstrip("/") + "/ingest"
    params: dict[str, Any] = {}
    if collector.human_baseline is not None:
        params["baseline"] = collector.human_baseline

    try:
        # Validate the JSON we send by round-tripping through the
        # contract — catches the case where a future field on the
        # collector drifts from the canonical schema.
        from contract import AgentObservation

        AgentObservation.model_validate(obs)
    except Exception as e:
        _log.warning("Observation failed contract validation: %s", e)
        return None

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=obs, params=params)
            r.raise_for_status()
    except Exception as e:
        _log.warning(
            "POST %s failed (%s). The run was captured but the dashboard "
            "will not show it. Set DPI_LS_DASHBOARD=0 to silence this.",
            url, e,
        )
        return None

    try:
        return r.json()
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return None


def write_local_copy(collector: SignalCollector, path: str | None = None) -> str:
    """Save the observation to disk for debugging / offline ingest.

    Returns the path written. Always succeeds.
    """
    if path is None:
        path = os.environ.get("DPI_LS_OBS_PATH") or "./dpi_ls_observation.json"
    obs = collector.to_observation()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obs, f, indent=2, default=str)
    except Exception as e:  # pragma: no cover - disk I/O
        _log.debug("Could not write local copy of observation: %s", e)
    return path
