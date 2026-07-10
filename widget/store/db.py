"""SQLAlchemy engine + Session management.

DATABASE_URL drives this. SQLite locally, Postgres in prod — the schema
is portable (JSON columns, no PG-specific types).
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_URL = "sqlite:///./dpi_ls.db"


class Base(DeclarativeBase):
    pass


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def configure(url: str | None = None) -> Engine:
    """(Re)bind the engine. Call this before init_db()."""
    global _engine, _SessionLocal
    url = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    is_sqlite = url.startswith("sqlite")
    is_memory = is_sqlite and ":memory:" in url

    connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    kwargs = {"connect_args": connect_args, "future": True}
    if is_memory:
        # Share the same in-memory DB across sessions for the duration
        # of the process.
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool

    _engine = create_engine(url, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        configure()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        configure()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    # Importing here ensures models are registered against Base before create_all.
    from . import models  # noqa: F401
    Base.metadata.create_all(get_engine())


def reset_db() -> None:
    """Test helper. Do not call in production."""
    from . import models  # noqa: F401
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
