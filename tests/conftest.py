"""Shared API test fixtures — fresh in-memory DB per test, isolated registry."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # Fresh in-memory DB for each test.
    from store import db as db_mod
    db_mod._engine = None  # type: ignore[attr-defined]
    db_mod._SessionLocal = None  # type: ignore[attr-defined]
    db_mod.configure("sqlite:///:memory:")
    db_mod.init_db()

    # Reset both ingestion registries — bootstrap re-registers everything.
    from ingestion import clear
    from ingestion.sources import clear as clear_sources
    clear()
    clear_sources()

    # Point bootstrap at fixtures/ so mapping_acme.yaml gets auto-registered
    # as `webhook:acme` during app startup.
    monkeypatch.setenv("MAPPINGS_DIR", str(Path(__file__).parent.parent / "fixtures"))

    from api.app import app
    with TestClient(app) as c:
        yield c
