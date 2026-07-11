"""FastAPI dependencies — DB session per request."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session


def db_session() -> Iterator[Session]:
    # Late import so a test fixture can re-configure the engine before
    # the first request lands.
    from store.db import get_session_factory

    SessionLocal = get_session_factory()
    with SessionLocal() as s:
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
