"""Phase 2 — Durable Execution Worker tests.

Tests the full execution lifecycle using an in-memory DB and a mocked
subprocess so the suite runs fast and offline.

Cases:
A. Submit execution -> execution_id returned
B. Status is QUEUED immediately after submit
C. Worker claims job -> status becomes RUNNING
D. Subprocess succeeds -> status becomes SUCCESS
E. Subprocess fails -> status becomes FAILED
F. Subprocess times out -> status becomes TIMEOUT
G. QUEUED job can be cancelled -> CANCELLED
H. RUNNING job cannot be cancelled (returns False from queue.cancel)
I. Duplicate execution guard (QUEUED/RUNNING job re-submit)
J. Unauthorized agent execution -> 403
K. Worker recovers orphaned RUNNING jobs on restart
L. API endpoint list/get executions
"""
from __future__ import annotations

import json
import os
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DISABLE_WORKER", "1")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _make_token(username: str = "alice", role: str = "USER") -> str:
    import jwt
    from datetime import datetime, timedelta, timezone
    return jwt.encode(
        {"sub": username, "role": role,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        "SUPER_SECRET_JWT_KEY_FOR_DPI_LS",
        algorithm="HS256",
    )


def _auth(username: str = "alice", role: str = "USER") -> dict:
    return {"Authorization": f"Bearer {_make_token(username, role)}"}


def _admin_auth() -> dict:
    return _auth("admin", "ADMIN")


# ---------------------------------------------------------------------------
# Shared client fixture with isolated in-memory DB
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path}/exec_test.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("DISABLE_WORKER", "1")

    import store.db as _db
    _db._engine = None
    _db._SessionLocal = None
    _db.configure(db_url)

    from api.app import app
    _db.init_db()

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    _db._engine = None
    _db._SessionLocal = None


@pytest.fixture()
def agent_id(client) -> str:
    """Create a test agent owned by alice via POST /api/agents."""
    aid = f"exec-test-{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/agents",
        json={"agent_id": aid, "agent_name": "Exec Test Agent"},
        headers=_auth("alice"),
    )
    assert r.status_code == 200, r.text
    return aid


# ---------------------------------------------------------------------------
# Standalone session factory for direct worker unit tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def sf(tmp_path, monkeypatch):
    """Isolated session factory using a temp DB — no shared state."""
    db_url = f"sqlite:///{tmp_path}/worker_test.db"
    monkeypatch.setenv("DATABASE_URL", db_url)

    import store.db as _db
    _db._engine = None
    _db._SessionLocal = None
    _db.configure(db_url)
    _db.init_db()

    factory = _db.get_session_factory()
    yield factory

    _db._engine = None
    _db._SessionLocal = None



# ---------------------------------------------------------------------------
# A. Submit execution -> execution_id returned
# B. Status is QUEUED immediately after submit
# ---------------------------------------------------------------------------

def test_submit_returns_queued(client, agent_id):
    r = client.post(f"/agents/{agent_id}/execute", headers=_auth("alice"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "execution_id" in body                      # A
    assert body["status"] == "QUEUED"                  # B
    assert body["agent_id"] == agent_id


# ---------------------------------------------------------------------------
# C. Worker claims job -> RUNNING
# D. Subprocess succeeds -> SUCCESS
# ---------------------------------------------------------------------------

def test_worker_success(sf):
    from worker.queue import enqueue, get_execution
    from worker.executor import process_one

    with sf() as s:
        exec_id = enqueue(s, "test-agent-success")

    with sf() as s:
        state = get_execution(s, exec_id)
    assert state["status"] == "QUEUED"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "ok"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        did_work = process_one(sf, base_url="http://127.0.0.1:9999")

    assert did_work is True                            # C (worker claimed it)

    with sf() as s:
        state = get_execution(s, exec_id)
    assert state["status"] == "SUCCESS"                # D
    assert state["exit_code"] == 0
    assert state["completed_at"] is not None


# ---------------------------------------------------------------------------
# E. Subprocess fails -> FAILED
# ---------------------------------------------------------------------------

def test_worker_failure(sf):
    from worker.queue import enqueue, get_execution
    from worker.executor import process_one

    with sf() as s:
        exec_id = enqueue(s, "test-agent-fail")

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "something went wrong"

    with patch("subprocess.run", return_value=mock_result):
        process_one(sf, base_url="http://127.0.0.1:9999")

    with sf() as s:
        state = get_execution(s, exec_id)
    assert state["status"] == "FAILED"                 # E
    assert "something went wrong" in (state["error"] or "")


# ---------------------------------------------------------------------------
# F. Timeout -> TIMEOUT
# ---------------------------------------------------------------------------

def test_worker_timeout(sf):
    import subprocess as _sp
    from worker.queue import enqueue, get_execution
    from worker.executor import process_one

    with sf() as s:
        exec_id = enqueue(s, "test-agent-timeout", timeout_seconds=1)

    with patch("subprocess.run", side_effect=_sp.TimeoutExpired(cmd="uv", timeout=1)):
        process_one(sf, base_url="http://127.0.0.1:9999")

    with sf() as s:
        state = get_execution(s, exec_id)
    assert state["status"] == "TIMEOUT"                # F


# ---------------------------------------------------------------------------
# G. Cancel QUEUED -> CANCELLED
# H. Cancel RUNNING -> False (can not cancel)
# ---------------------------------------------------------------------------

def test_cancel_queued_via_api(client, agent_id):
    r = client.post(f"/agents/{agent_id}/execute", headers=_auth("alice"))
    exec_id = r.json()["execution_id"]

    rc = client.post(
        f"/agents/{agent_id}/executions/{exec_id}/cancel",
        headers=_auth("alice"),
    )
    assert rc.status_code == 200                       # G
    assert rc.json()["status"] == "CANCELLED"


def test_cancel_running_returns_false(sf):
    from store.models import ExecutionRow
    from worker.queue import cancel

    exec_id = str(uuid.uuid4())
    with sf() as s:
        row = ExecutionRow(
            id=exec_id, agent_id="x", status="RUNNING",
            queued_at=time.time(), started_at=time.time(),
        )
        s.add(row)
        s.commit()

    with sf() as s:
        ok = cancel(s, exec_id)
    assert ok is False                                 # H


# ---------------------------------------------------------------------------
# I. Duplicate execution guard
# ---------------------------------------------------------------------------

def test_duplicate_execution_guard(client, agent_id):
    r1 = client.post(f"/agents/{agent_id}/execute", headers=_auth("alice"))
    r2 = client.post(f"/agents/{agent_id}/execute", headers=_auth("alice"))
    assert r1.json()["execution_id"] == r2.json()["execution_id"]  # I
    assert "duplicate" in r2.json().get("message", "").lower()


# ---------------------------------------------------------------------------
# J. Unauthorized agent execution -> 403
# ---------------------------------------------------------------------------

def test_unauthorized_execute_returns_403(client, agent_id):
    # bob does not own agent_id (alice owns it)
    r = client.post(f"/agents/{agent_id}/execute", headers=_auth("bob"))
    assert r.status_code == 403                        # J


# ---------------------------------------------------------------------------
# K. Worker recovers orphaned RUNNING jobs on restart
# ---------------------------------------------------------------------------

def test_orphan_recovery(sf):
    from store.models import ExecutionRow
    from worker.executor import recover_orphans

    orphan_id = str(uuid.uuid4())
    dead_pid = 99999999  # virtually guaranteed not to exist

    with sf() as s:
        row = ExecutionRow(
            id=orphan_id,
            agent_id="orphan-agent",
            status="RUNNING",
            queued_at=time.time(),
            started_at=time.time(),
            worker_pid=dead_pid,
        )
        s.add(row)
        s.commit()

    recovered = recover_orphans(sf)
    assert recovered == 1                              # K (only our orphan in isolated DB)

    from worker.queue import get_execution
    with sf() as s:
        state = get_execution(s, orphan_id)
    assert state["status"] == "FAILED"
    assert "recovered" in (state["error"] or "")


# ---------------------------------------------------------------------------
# L. List / get executions endpoints
# ---------------------------------------------------------------------------

def test_list_and_get_executions(client, agent_id):
    r = client.post(f"/agents/{agent_id}/execute", headers=_auth("alice"))
    exec_id = r.json()["execution_id"]

    # List
    lr = client.get(f"/agents/{agent_id}/executions", headers=_auth("alice"))
    assert lr.status_code == 200
    items = lr.json()
    assert any(e["execution_id"] == exec_id for e in items)

    # Get single
    gr = client.get(f"/agents/{agent_id}/executions/{exec_id}", headers=_auth("alice"))
    assert gr.status_code == 200
    assert gr.json()["execution_id"] == exec_id
    assert gr.json()["status"] == "QUEUED"
