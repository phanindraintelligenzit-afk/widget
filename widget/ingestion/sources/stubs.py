"""Stubs for the source adapters parked until M5+ work them out.

Each one registers under its source name and accepts the same payload
contract as a SourceAdapter, but returns an empty partial list with a
documented "not implemented yet" log line on the first call. The point
is to prove the interface is in place — onboarding a real adapter is
swapping the body of to_partials(), not changing engine, store, or API.
"""
from __future__ import annotations

import logging
from typing import Any

from contract import PartialObservation

from .base import SourceAdapter

_log = logging.getLogger(__name__)


class _StubAdapter(SourceAdapter):
    """Base for not-yet-implemented sources."""
    _warned = False

    def to_partials(self, payload: Any) -> list[PartialObservation]:
        if not type(self)._warned:
            _log.warning(
                "Source adapter '%s' is a stub — onboarding is the next "
                "milestone. Returning no partials.",
                self.name,
            )
            type(self)._warned = True
        return []


ALL_STUBS = ()
