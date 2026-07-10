"""dpi_ls — the installable package entry point.

Public surface (kept tiny on purpose — anything else is private to the
package):

* :func:`monitor` — instrument any agent in two lines.
* :class:`SignalCollector` — exposed for tests and for advanced users
  who want to push signals into a collector from a custom framework
  patcher.
* :mod:`evaluator` — the LangGraph Q evaluator, exposed for tests and
  for users who want to score a list of outputs directly.

Usage::

    import dpi_ls
    dpi_ls.monitor(agent, agent_id="my-agent")
    # ... rest of the user's existing script unchanged ...
"""
from __future__ import annotations

# Re-export the public API. ``monitor`` is the headline — everything
# else is a building block users can reach for if they need to.
from .collector import SignalCollector
from .evaluator import QResult, evaluate_quality
from .monitor import monitor

__all__ = [
    "QResult",
    "SignalCollector",
    "evaluate_quality",
    "monitor",
]
