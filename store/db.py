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
import json
import boto3

class Base(DeclarativeBase):
    pass


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def get_db_secret(secret_name: str) -> str:
    """Fetch database credentials from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    # Construct Postgres URL from secret
    user = secret.get("username", "")
    password = secret.get("password", "")
    host = secret.get("host", "localhost")
    port = secret.get("port", "5432")
    dbname = secret.get("dbname", "dpi_ls")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"


def configure(url: str | None = None) -> Engine:
    """(Re)bind the engine. Call this before init_db()."""
    global _engine, _SessionLocal
    dpi_env = os.environ.get("DPI_ENV", "development")
    
    # 1. Resolve connection URL
    if not url:
        url = os.environ.get("DPI_DB_URL")
        # In production, if DPI_DB_URL isn't explicitly set (e.g. for a proxy), fetch from Secrets Manager
        if not url and dpi_env == "production":
            secret_name = os.environ.get("DPI_DB_SECRET_NAME", "dpi-ls/production/database")
            try:
                url = get_db_secret(secret_name)
            except Exception as e:
                raise RuntimeError(f"Failed to fetch DB credentials from Secrets Manager: {e}")
        elif not url:
            url = DEFAULT_URL

    # 2. Hard production guard: Fail loud, never fall back.
    if dpi_env == "production":
        if "sqlite" in url or "localhost" in url:
            raise RuntimeError(f"Startup assertion failed: DPI_ENV=production but resolved DB URL points to local/sqlite: {url}")

    is_sqlite = url.startswith("sqlite")
    is_memory = is_sqlite and ":memory:" in url

    connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    kwargs = {"connect_args": connect_args, "future": True}
    if is_memory:
        # Share the same in-memory DB across sessions for the duration
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
