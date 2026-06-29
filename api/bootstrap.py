"""Startup helpers: configure DB, register stock adapters, scan mappings dir."""
from __future__ import annotations

import os
from pathlib import Path

from ingestion import (
    FieldMapping,
    GenericWebhookAdapter,
    list_adapters,
    register,
)


def register_stock_adapters() -> None:
    # All source adapters self-register; idempotent.
    from ingestion.sources import register_all
    register_all()


def register_mappings_from_dir(directory: str | Path) -> list[str]:
    """Scan a folder for `mapping_*.yaml` and register each as
    `webhook:<name>` against GenericWebhookAdapter. Returns adapter
    names registered.
    """
    d = Path(directory)
    registered: list[str] = []
    if not d.exists():
        return registered
    for f in sorted(d.glob("mapping_*.yaml")):
        source = f.stem.removeprefix("mapping_")
        name = f"webhook:{source}"
        adapter = GenericWebhookAdapter(FieldMapping.from_yaml(f), name=name)
        register(adapter, replace=True)
        registered.append(name)
    return registered


def bootstrap() -> None:
    """Configure DB + register adapters. Idempotent."""
    from store import db as db_mod

    if db_mod._engine is None:  # type: ignore[attr-defined]
        db_mod.configure()
    db_mod.init_db()
    register_stock_adapters()
    mappings_dir = os.environ.get("MAPPINGS_DIR")
    if mappings_dir:
        register_mappings_from_dir(mappings_dir)

    # Seed and run initial evaluations for the Cost Resource Evaluation framework
    session_factory = db_mod.get_session_factory()
    with session_factory() as session:
        try:
            from dpi_ls.cost_resource_evaluation_service import CostResourceEvaluationService
            service = CostResourceEvaluationService(session)
            service.register_resources()
            service.run_evaluations()
            session.commit()

            # Pre-populate Prometheus Gauges with the latest scores from DB on startup
            from api.scoring import update_prometheus_metrics
            from store import repo
            for agent_row, score_row in repo.latest_scores_for_all(session):
                if score_row:
                    from contract import Rating
                    rating = Rating(
                        score=score_row.score,
                        raw_score=score_row.raw_score,
                        band=score_row.band,
                        unsafe=score_row.unsafe,
                        gate_failures=score_row.gate_failures,
                        metrics=score_row.metrics,
                        sub_metrics=score_row.sub_metrics,
                        missing=score_row.missing,
                    )
                    update_prometheus_metrics(agent_row.id, rating)
        except Exception as e:
            # Prevent startup failure if DB is locked/uninitialized during schema migration/testing
            print(f"Error seeding cost resource registry: {e}")
            session.rollback()

