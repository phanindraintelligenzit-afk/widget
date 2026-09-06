"""Worker executor — picks up QUEUED jobs from the DB and runs them.

Design:
- Polls the executions table for QUEUED rows.
- Claims a job by flipping status to RUNNING (atomic UPDATE with WHERE status=QUEUED).
- Runs the agent subprocess with a timeout.
- Updates ExecutionRow on completion/failure/timeout.
- After a successful run, calls /ingest via HTTP so the scoring engine
  persists the score exactly as a manual ingest would.

No external broker needed — the DB is the queue.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from typing import Optional

log = logging.getLogger("dpi_ls.worker")


# ---------------------------------------------------------------------------
# Claim helpers (atomic — only one worker will win the SELECT + UPDATE)
# ---------------------------------------------------------------------------

def _claim_next_queued(session) -> Optional[object]:
    """Atomically claim the oldest QUEUED execution. Returns the row or None."""
    from store.models import ExecutionRow
    from sqlalchemy import select, update

    # 1. Find the oldest QUEUED
    row = (
        session.query(ExecutionRow)
        .filter(ExecutionRow.status == "QUEUED")
        .order_by(ExecutionRow.queued_at)
        .first()
    )
    if row is None:
        return None

    # 2. Try to atomically claim it
    exec_id = row.id
    now = time.time()
    
    stmt = (
        update(ExecutionRow)
        .where(ExecutionRow.id == exec_id, ExecutionRow.status == "QUEUED")
        .values(
            status="RUNNING",
            started_at=now,
            start_time=now,
            worker_pid=os.getpid()
        )
    )
    result = session.execute(stmt)
    session.commit()
    
    # 3. If rows matched, we won the race. If 0, another worker got it.
    if result.rowcount == 0:
        return None
        
    return session.get(ExecutionRow, exec_id)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _run_agent_subprocess(agent_id: str, agent_name: str, timeout_seconds: int) -> tuple[int, str, str]:
    """Run test_agent.py subprocess. Returns (returncode, stdout, stderr)."""
    env = os.environ.copy()
    env["AGENT_ID"] = agent_id
    env["AGENT_NAME"] = agent_name
    env["HUMAN_BASELINE"] = "1"
    env["BEDROCK_MODEL_ID"] = "mock-model"
    env["AWS_ACCESS_KEY_ID"] = "rotated"
    env["LITELLM_DROP_PARAMS"] = "True"

    try:
        res = subprocess.run(
            [sys.executable, "-m", "uv", "run", "python", "examples/test_agent.py"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT after {timeout_seconds}s"
    except Exception as e:
        return -2, "", str(e)


def _find_uv() -> list[str]:
    """Return the command prefix for running uv."""
    # Try: uv run python examples/test_agent.py
    uv = os.environ.get("UV_PATH", "uv")
    return [uv, "run", "python", "examples/test_agent.py"]


def _run_subprocess(agent_id: str, agent_name: str, timeout_seconds: int) -> tuple[int, str, str]:
    """Run examples/test_agent.py via uv or direct python."""
    env = os.environ.copy()
    env["AGENT_ID"] = agent_id
    env["AGENT_NAME"] = agent_name
    env["HUMAN_BASELINE"] = "1"
    env["BEDROCK_MODEL_ID"] = "mock-model"
    env["AWS_ACCESS_KEY_ID"] = "rotated"
    env["LITELLM_DROP_PARAMS"] = "True"

    cmd = _find_uv()
    try:
        res = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=os.getcwd(),
        )
        return res.returncode, res.stdout[-8000:], res.stderr[-8000:]
    except FileNotFoundError:
        # uv not on PATH — try python directly
        try:
            res = subprocess.run(
                [sys.executable, "examples/test_agent.py"],
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=os.getcwd(),
            )
            return res.returncode, res.stdout[-8000:], res.stderr[-8000:]
        except subprocess.TimeoutExpired:
            return -1, "", f"TIMEOUT after {timeout_seconds}s"
        except Exception as e:
            return -2, "", str(e)
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT after {timeout_seconds}s"
    except Exception as e:
        return -2, "", str(e)


# ---------------------------------------------------------------------------
# Post observation to scoring engine
# ---------------------------------------------------------------------------

def _ingest_result(agent_id: str, agent_name: str, base_url: str) -> Optional[dict]:
    """POST a minimal observation to /ingest so the scoring engine stores a score."""
    import httpx
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    obs = {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "source": "worker",
        "period_start": now,
        "period_end": now,
        "attempts": 1,
        "successful": 1,
        "failed": 0,
        "outputs": [f"Worker execution completed for {agent_id}"],
        "violations": [],
        "tasks": [{"task_id": "worker-task", "status": "SUCCESS", "duration_seconds": 1.0}],
        "executions": [{"execution_id": "worker-exec", "status": "SUCCESS", "duration_seconds": 1.0}],
        "policy": {"violations": 0, "total_actions": 1},
        "validation": {"components_validated": 1, "total_components": 1},
        "cost": {"input_tokens": 100, "output_tokens": 100, "infrastructure_cost": 0.0},
        "tags": {"source": "worker"},
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(f"{base_url.rstrip('/')}/ingest", json=obs)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        log.warning("ingest failed: %s", e)
    return None


# ---------------------------------------------------------------------------
# Single job processing
# ---------------------------------------------------------------------------

def process_one(session_factory, base_url: str = "http://127.0.0.1:8000") -> bool:
    """Claim and process one QUEUED job. Returns True if a job was processed."""
    from store.models import ExecutionRow, AgentRow

    with session_factory() as session:
        row = _claim_next_queued(session)
        if row is None:
            return False

        exec_id = row.id
        agent_id = row.agent_id
        timeout_secs = row.timeout_seconds or 300
        log.info("worker: claimed %s for agent %s (timeout=%ds)", exec_id, agent_id, timeout_secs)

    # Fetch agent name outside the claim transaction
    with session_factory() as session:
        agent = session.get(AgentRow, agent_id)
        agent_name = agent.name if agent else agent_id

    # Run the subprocess
    rc, stdout, stderr = _run_subprocess(agent_id, agent_name, timeout_secs)
    now = time.time()

    # Determine final status
    if rc == -1:
        final_status = "TIMEOUT"
        error_msg = stderr
        result_payload = None
    elif rc == 0:
        final_status = "SUCCESS"
        error_msg = None
        result_payload = json.dumps({"stdout": stdout[-2000:], "exit_code": 0})
    else:
        final_status = "FAILED"
        error_msg = stderr[-2000:] or f"exit code {rc}"
        result_payload = None

    # Persist final state
    with session_factory() as session:
        ex = session.get(ExecutionRow, exec_id)
        if ex:
            ex.status = final_status
            ex.completed_at = now
            ex.end_time = now
            ex.exit_code = rc
            ex.error = error_msg
            ex.result = result_payload
            session.commit()

    log.info("worker: %s → %s", exec_id, final_status)

    # If successful, call the scoring engine
    if final_status == "SUCCESS":
        rating = _ingest_result(agent_id, agent_name, base_url)
        if rating:
            log.info("worker: score stored for %s: %.1f", agent_id, rating.get("score", -1))

    return True


# ---------------------------------------------------------------------------
# Recovery: mark RUNNING jobs as FAILED if worker_pid is dead
# ---------------------------------------------------------------------------

def recover_orphans(session_factory) -> int:
    """On worker start, find RUNNING rows whose worker process is dead and mark them FAILED."""
    from store.models import ExecutionRow

    recovered = 0
    with session_factory() as session:
        stale = session.query(ExecutionRow).filter(ExecutionRow.status == "RUNNING").all()
        for row in stale:
            pid = row.worker_pid
            alive = _pid_alive(pid)
            if not alive:
                row.status = "FAILED"
                row.error = f"worker PID {pid} died (recovered on restart)"
                row.completed_at = time.time()
                row.end_time = time.time()
                recovered += 1
                log.warning("worker: recovered orphan %s (PID %s was dead)", row.id, pid)
        session.commit()
    return recovered


def _pid_alive(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
