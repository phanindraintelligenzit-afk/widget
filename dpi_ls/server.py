"""Background FastAPI server launcher.

``start_server()`` boots the existing ``api.app:app`` FastAPI application
inside a daemon thread. Returns once the server is reachable on
``/healthz``, so callers (the package's ``monitor()`` entrypoint, tests)
can hand off control to the user's script and rely on the dashboard
being live.

Design notes:

* The server thread is ``daemon=True`` so the interpreter can shut down
  cleanly without the worker blocking process exit. The process only
  exits because the user's script is done — and we keep the user's
  script alive with a stdin block in ``monitor()``.

* A tiny HTTP probe (urllib, not httpx — keeps the boot path dep-free)
  polls ``/healthz`` until the server is up or the timeout fires. The
  first import of FastAPI + SQLAlchemy can take a couple of seconds on
  a cold start.

* Idempotent: calling ``start_server()`` twice is a no-op.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
import time
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import Optional

_log = logging.getLogger("dpi_ls.server")

# Cap how long we'll wait for the server to come up. 30 s is generous —
# if the import chain takes longer, something is wrong and the user
# will see the real error from their agent run.
_STARTUP_TIMEOUT_S = 30.0

# Singleton state — the launcher is process-wide. Re-entrant calls
# (e.g. test fixtures that exercise the API directly and then call
# monitor() too) are no-ops.
_lock = threading.Lock()
_server_thread: Optional[threading.Thread] = None
_server_info: Optional["ServerInfo"] = None
_url_lock = threading.Lock()  # for the post() poster — see poster.py


@dataclass(frozen=True)
class ServerInfo:
    host: str
    port: int
    base_url: str


def start_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    open_browser: bool = False,
    database_url: str | None = None,
) -> ServerInfo:
    """Boot the DPI-LS dashboard in a background thread. Returns the URL.

    Re-entrant: returns the existing ``ServerInfo`` if a server is
    already running. The ``database_url`` argument is honoured only on
    the first call; subsequent calls reuse the running server.
    """
    global _server_thread, _server_info
    with _lock:
        if _server_thread is not None and _server_thread.is_alive():
            assert _server_info is not None
            return _server_info

        # If the port is already bound (e.g. user started uvicorn manually
        # or another dpi_ls process is running), reuse it silently rather
        # than crashing the daemon thread with an "address in use" error.
        if is_port_in_use(host, port):
            _log.info(
                "dpi_ls: port %d already in use — reusing existing server at "
                "http://%s:%d", port, host, port,
            )
            info = ServerInfo(host=host, port=port, base_url=f"http://{host}:{port}")
            _server_info = info
            return info

        # Database config — set BEFORE the app imports, because
        # ``store.db.configure()`` binds the engine on first call.
        if database_url is None:
            database_url = os.environ.get("DPI_LS_DATABASE_URL") or _default_db_url()
        os.environ["DATABASE_URL"] = database_url

        info = ServerInfo(host=host, port=port, base_url=f"http://{host}:{port}")
        _server_info = info
        _server_thread = threading.Thread(
            target=_run_server,
            args=(info,),
            name="dpi-ls-server",
            daemon=True,
        )
        _server_thread.start()

    # Wait for the server to accept connections — outside the lock so
    # other callers don't queue on us.
    _wait_until_ready(info)
    if open_browser:
        try:
            webbrowser.open(info.base_url + "/")
        except Exception:  # pragma: no cover
            _log.debug("webbrowser.open failed", exc_info=True)
    return info


def current_server() -> Optional[ServerInfo]:
    """The running server's URL, or None if ``start_server`` hasn't been called."""
    return _server_info


def is_port_in_use(host: str, port: int) -> bool:
    """Cheap "is anyone listening on this port?" check used by tests."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _run_server(info: ServerInfo) -> None:
    """Worker thread target. Runs uvicorn forever (until process exit)."""
    try:
        import uvicorn
    except ImportError:  # pragma: no cover - uvicorn is in pyproject deps
        _log.error("uvicorn is not installed; the dashboard cannot start.")
        return

    # We import the app lazily so the bootstrap (DB config, adapter
    # registration) happens inside the worker thread and never races
    # with the main thread.
    from api.app import app  # noqa: WPS433 - intentional runtime import

    config = uvicorn.Config(
        app,
        host=info.host,
        port=info.port,
        log_level="warning",
        access_log=False,
        # No reload — we're a child of the user's script.
        reload=False,
        # Use the default asyncio loop. ``uvicorn.Server.serve()`` is
        # safe to run from a non-main thread.
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    except Exception:  # pragma: no cover - server crashed
        _log.exception("DPI-LS dashboard server crashed.")


def _wait_until_ready(info: ServerInfo, timeout: float = _STARTUP_TIMEOUT_S) -> None:
    """Poll ``/healthz`` until the server responds (or we give up)."""
    deadline = time.monotonic() + timeout
    url = info.base_url + "/healthz"
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as r:  # noqa: S310
                if r.status == 200:
                    _log.debug("DPI-LS dashboard is live at %s", info.base_url)
                    return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.1)
    _log.warning(
        "DPI-LS dashboard did not come up within %.1fs (last error: %s). "
        "The agent run will still be scored, but the dashboard may be "
        "unreachable. URL was %s",
        timeout, last_err, info.base_url,
    )


def _default_db_url() -> str:
    """Per-user default DB location. Falls back to a local SQLite file
    in the current working directory for backwards compatibility with
    the existing demo (``./dpi_ls.db``)."""
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    return "sqlite:///./dpi_ls.db"
