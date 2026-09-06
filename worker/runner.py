"""DPI-LS Worker runner — poll-based durable task processor.

Usage (standalone process):
    uv run python -m worker.runner

Usage (embedded daemon thread for development):
    from worker.runner import start_worker_thread
    t = start_worker_thread()

The worker:
1. Recovers orphaned RUNNING jobs from previous crashes on startup.
2. Polls the executions table every POLL_INTERVAL_S for QUEUED jobs.
3. Processes one job at a time (extend to N threads for parallelism).
4. Never crashes the main loop on individual job failures.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time

log = logging.getLogger("dpi_ls.worker")

POLL_INTERVAL_S = float(os.environ.get("WORKER_POLL_INTERVAL", "2.0"))
BASE_URL = os.environ.get("DPI_LS_BASE_URL", "http://127.0.0.1:8000")

_stop_event = threading.Event()


def _setup_signals():
    """Graceful shutdown on SIGINT / SIGTERM."""
    def _handler(sig, frame):
        log.info("worker: received signal %s — shutting down", sig)
        _stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    try:
        signal.signal(signal.SIGTERM, _handler)
    except (AttributeError, OSError):
        pass  # Windows


def run_forever(poll_interval: float = POLL_INTERVAL_S, base_url: str = BASE_URL):
    """Main worker loop. Blocks until _stop_event is set."""
    from store import db as store_db
    from worker.executor import process_one, recover_orphans

    store_db.init_db()
    sf = store_db.get_session_factory()

    log.info("worker: starting — poll=%.1fs  base_url=%s", poll_interval, base_url)
    recovered = recover_orphans(sf)
    if recovered:
        log.info("worker: recovered %d orphaned executions", recovered)

    while not _stop_event.is_set():
        try:
            did_work = process_one(sf, base_url=base_url)
        except Exception as exc:
            log.exception("worker: unhandled error in process_one: %s", exc)
            did_work = False

        if not did_work:
            # Nothing to do — sleep before next poll
            _stop_event.wait(timeout=poll_interval)

    log.info("worker: stopped")


def start_worker_thread(
    poll_interval: float = POLL_INTERVAL_S,
    base_url: str = BASE_URL,
    daemon: bool = True,
) -> threading.Thread:
    """Start the worker in a background daemon thread. Returns the thread."""
    t = threading.Thread(
        target=run_forever,
        kwargs={"poll_interval": poll_interval, "base_url": base_url},
        name="dpi-ls-worker",
        daemon=daemon,
    )
    t.start()
    return t


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    _setup_signals()
    run_forever()
