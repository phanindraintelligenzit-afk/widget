import json
from typing import Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from store.models import ScoreTraceRow

class ScoreTrace(BaseModel):
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    normalization: list[dict[str, Any]] = Field(default_factory=list)
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    aggregation: dict[str, Any] = Field(default_factory=dict)
    gates: list[dict[str, Any]] = Field(default_factory=list)
    band: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

def build_trace(
    agent_id: str,
    run_id: str,
    metrics: dict[str, Optional[float]],
    weighted_metrics: dict[str, float],
    weights_used: dict[str, float],
    gate_thresholds: dict[str, float],
    gate_failures: list[str],
    raw_score: float,
    final_score: float,
    band_label: str,
    config_version: str,
) -> ScoreTrace:
    # A simple build_trace that captures what is requested
    dims = []
    prov = {}
    for k in ["P", "Q", "E", "G", "R", "C", "V"]:
        val = metrics.get(k)
        w = weights_used.get(k, 0.0)
        dims.append({
            "dimension": k,
            "score": val,
            "weight": w,
            "config_version": config_version
        })
        prov[k] = "measured" if val is not None else "default"

    gates = []
    for k, t in (gate_thresholds or {}).items():
        v = metrics.get(k)
        gates.append({
            "gate": k,
            "threshold": t,
            "observed_value": v,
            "pass": k not in gate_failures
        })

    aggregation = {
        "formula": "PI = (P * Q * 1.5E) + (G * 1.5R) + (C * V)",
        "term1": weighted_metrics.get("term1", 0.0),
        "term2": weighted_metrics.get("term2", 0.0),
        "term3": weighted_metrics.get("term3", 0.0),
        "pre_band_score": raw_score,
    }

    return ScoreTrace(
        dimensions=dims,
        aggregation=aggregation,
        gates=gates,
        band={"label": band_label},
        provenance=prov,
        inputs=[],
        normalization=[]
    )

def persist_trace(
    session: Session,
    run_id: str,
    config_version: str,
    final_score: float,
    trace: ScoreTrace
) -> None:
    try:
        row = ScoreTraceRow(
            run_id=run_id,
            config_version=config_version,
            final_score=final_score,
            trace=trace.model_dump()
        )
        session.merge(row)
        session.commit()
    except Exception as e:
        session.rollback()
        import logging
        logging.getLogger(__name__).warning(f"Failed to persist trace for run {run_id}: {e}")
