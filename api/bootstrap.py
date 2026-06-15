"""Startup helpers: configure DB, register stock adapters, scan mappings dir."""
from __future__ import annotations

import os
from pathlib import Path

from ingestion import (
    FieldMapping,
    GenericWebhookAdapter,
    OTelAdapter,
    list_adapters,
    register,
)


def register_stock_adapters() -> None:
    if "otel" not in list_adapters():
        register(OTelAdapter())
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

    # Register dynamic validation and cost metrics
    from store.db import get_session_factory
    from dpi_ls.validation_service import register_standard_metrics as reg_val_metrics
    from dpi_ls.cost_service import register_standard_metrics as reg_cost_metrics
    session_factory = get_session_factory()
    with session_factory() as s:
        reg_val_metrics(s)
        reg_cost_metrics(s)
        s.commit()

    register_stock_adapters()
    mappings_dir = os.environ.get("MAPPINGS_DIR")
    if mappings_dir:
        register_mappings_from_dir(mappings_dir)
