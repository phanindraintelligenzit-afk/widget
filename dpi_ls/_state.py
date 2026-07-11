"""Process-wide state for the dpi_ls package.

A small, explicit module so we don't sprinkle module-level globals
across the package. ``monitor()`` writes to these; the atexit
finalizer reads from them. Tests reset them between runs.
"""
from __future__ import annotations

import threading
from typing import Optional

from .collector import SignalCollector
from .server import ServerInfo

# Lock for any field that is written from the user's main thread and
# read from the atexit finalizer (which runs on the main thread too
# in CPython, but threading.Lock makes the intent explicit).
_state_lock = threading.Lock()

# The single collector for the current run. ``monitor()`` overwrites
# it on a second call (rare in practice — usually one agent per
# process), and the atexit finalizer resets it after post.
_collector: Optional[SignalCollector] = None

# Server info for the running background server, if any.
_server_info: Optional[ServerInfo] = None

# Bookkeeping for the finalizer — see monitor.py. Multiple atexit
# handlers are allowed in Python but we only want one.
_finalizer_registered: bool = False

# Test escape hatch — disable posting / blocking without affecting
# production behavior.
_block_on_exit: bool = True
_post_on_exit: bool = True


def get_collector() -> Optional[SignalCollector]:
    return _collector


def set_collector(c: Optional[SignalCollector]) -> None:
    global _collector
    with _state_lock:
        _collector = c


def get_server_info() -> Optional[ServerInfo]:
    return _server_info


def set_server_info(info: Optional[ServerInfo]) -> None:
    global _server_info
    with _state_lock:
        _server_info = info


def finalizer_registered() -> bool:
    return _finalizer_registered


def mark_finalizer_registered() -> None:
    global _finalizer_registered
    with _state_lock:
        _finalizer_registered = True


def reset_for_tests() -> None:
    """Clear state. Tests call this in their fixtures so each test
    starts from a known empty state."""
    global _collector, _server_info, _finalizer_registered
    global _block_on_exit, _post_on_exit
    with _state_lock:
        _collector = None
        _server_info = None
        _finalizer_registered = False
        _block_on_exit = True
        _post_on_exit = True


def set_block_on_exit(value: bool) -> None:
    global _block_on_exit
    with _state_lock:
        _block_on_exit = value


def get_block_on_exit() -> bool:
    return _block_on_exit


def set_post_on_exit(value: bool) -> None:
    global _post_on_exit
    with _state_lock:
        _post_on_exit = value


def get_post_on_exit() -> bool:
    return _post_on_exit
