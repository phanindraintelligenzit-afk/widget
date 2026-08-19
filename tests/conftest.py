"""Shared API test fixtures — fresh in-memory DB per test, isolated registry."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import os
    os.environ["TESTING"] = "1"
    
    # Fresh in-memory DB for each test.
    from store import db as db_mod
    db_mod._engine = None  # type: ignore[attr-defined]
    db_mod._SessionLocal = None  # type: ignore[attr-defined]
    db_mod.configure("sqlite:///:memory:")
    db_mod.init_db()

    # Seed app_settings so uncalibrated engine check passes in tests
    from store.models import SettingsRow
    with db_mod.get_session_factory()() as s:
        s.add(SettingsRow(
            id=1,
            payload={
                "weights": {"P": 0.15, "Q": 0.20, "E": 0.15, "G": 0.20, "R": 0.15, "C": 0.05, "V": 0.10},
                "q_sub_weights": {"accuracy": 0.70, "consistency": 0.20, "hallucination": 0.10},
                "gate_thresholds": {"G": 0.60, "R": 0.70, "V": 0.60},
                "r_max": 50.0,
                "human_cost_per_output": 50.0,
                "utilization": 1.0,
                "normalization_factor": 1.0,
                "input_token_price": 0.000005,
                "output_token_price": 0.000015,
                "ground_truth_dataset_path": None,
            }
        ))
        s.commit()

    # Reset both ingestion registries — bootstrap re-registers everything.
    from ingestion import clear
    from ingestion.sources import clear as clear_sources
    clear()
    clear_sources()

    # Point bootstrap at fixtures/ so mapping_acme.yaml gets auto-registered
    # as `webhook:acme` during app startup.
    monkeypatch.setenv("MAPPINGS_DIR", str(Path(__file__).parent.parent / "fixtures"))


    from api.app import app, get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"username": "testadmin", "role": "ADMIN"}
    
    with TestClient(app) as c:

        yield c
        
        from dpi_ls import _state
        _state.reset_for_tests()
        from dpi_ls.enterprise_validation_evaluation_service import reset_enterprise_validation_collector
        reset_enterprise_validation_collector()
        from store.db import get_session_factory
        with get_session_factory()() as s:
            from store.models import EnterpriseValidationResourceEvaluationRow
            s.query(EnterpriseValidationResourceEvaluationRow).delete()
            s.commit()

