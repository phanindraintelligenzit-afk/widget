"""DB-backed durable task queue for DPI-LS executions.

Uses the executions table (ExecutionRow) as the queue store.
No external broker required — the database IS the queue.

Survives API server restarts: QUEUED jobs remain in the DB until
a worker picks them up, regardless of which API process wrote them.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from sqlalchemy.orm import Session


def enqueue(
    session: Session,
    agent_id: str,
    timeout_seconds: int = 300,
) -> str:
    """Create a QUEUED execution record and return its execution_id."""
    from store.models import ExecutionRow

    execution_id = str(uuid.uuid4())
    now = time.time()
    row = ExecutionRow(
        id=execution_id,
        agent_id=agent_id,
        status="QUEUED",
        queued_at=now,
        start_time=now,          # keep legacy col in sync
        timeout_seconds=timeout_seconds,
        retry_count=0,
    )
    session.add(row)
    session.commit()
    return execution_id


def cancel(session: Session, execution_id: str, cancelled_by: str = "system") -> bool:
    """Cancel a QUEUED execution. Returns True if cancelled, False if already past QUEUED."""
    from store.models import ExecutionRow

    row = session.get(ExecutionRow, execution_id)
    if row is None:
        return False
    if row.status != "QUEUED":
        return False  # Can't cancel a job that's already running/done
    row.status = "CANCELLED"
    row.cancelled_by = cancelled_by
    row.completed_at = time.time()
    row.end_time = time.time()
    session.commit()
    return True


def get_execution(session: Session, execution_id: str) -> Optional[dict]:
    """Return the current state of an execution as a dict."""
    from store.models import ExecutionRow

    row = session.get(ExecutionRow, execution_id)
    if row is None:
        return None
    return _row_to_dict(row)


def list_executions(session: Session, agent_id: str) -> list[dict]:
    """Return all executions for an agent, newest first."""
    from store.models import ExecutionRow
    from sqlalchemy import desc

    rows = (
        session.query(ExecutionRow)
        .filter(ExecutionRow.agent_id == agent_id)
        .order_by(desc(ExecutionRow.queued_at))
        .all()
    )
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> dict:
    return {
        "execution_id": row.id,
        "agent_id": row.agent_id,
        "status": row.status,
        "queued_at": row.queued_at,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "timeout_seconds": row.timeout_seconds,
        "exit_code": row.exit_code,
        "error": row.error,
        "result": row.result,
        "cancelled_by": row.cancelled_by,
        "worker_pid": row.worker_pid,
        "retry_count": row.retry_count,
    }
