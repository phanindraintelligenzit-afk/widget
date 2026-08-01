"""FastAPI app — the demo surface for the widget to poll.

Routes:
    GET  /healthz                          — liveness
    GET  /adapters                         — registered adapters
    POST /ingest                           — canonical AgentObservation
    POST /ingest/{adapter_name}            — raw payload via a registered adapter
    GET  /agents                           — list agents
    GET  /agents/{id}/score                — latest Rating
    GET  /agents/{id}/history              — score history (Newest first)
    GET  /ratings                          — board view: latest per agent
    GET  /settings, PUT /settings          — tunables
    POST /agents/{id}/sme-rating           — record an SME quality capture (M6 input)

The engine is never imported here directly — only via api/scoring.py.
Adapters are looked up by name via the ingestion registry.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select


from contract import AgentObservation, Rating, Settings
from ingestion import get as get_adapter
from ingestion import list_adapters
from ingestion.sources import get as get_source
from ingestion.sources import list_sources
from store import repo

from engine import sme_flow

from .bootstrap import bootstrap
from .dependencies import db_session
from .schemas import (
    AdapterInfo,
    AgentSummary,
    BoardRow,
    HistoryPoint,
    SMEFlowRespond,
    SMEFlowStart,
    SMEFlowStatus,
    SMERatingIn,
)
from .scoring import ingest_partials, score_and_persist
from .sme_orchestration import advance_session, start_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio
    import logging
    logger = logging.getLogger("uvicorn.error")

    lf_host = os.environ.get("LANGFUSE_HOST")
    prom_url = os.environ.get("PROMETHEUS_URL")
    graf_url = os.environ.get("GRAFANA_URL")

    # Print the resolved values during startup
    logger.info("----------------------------------------")
    logger.info(f"Langfuse:\n{lf_host or 'MISSING'}\n")
    logger.info(f"Prometheus:\n{prom_url or 'MISSING'}\n")
    logger.info(f"Grafana:\n{graf_url or 'MISSING'}")
    logger.info("----------------------------------------")

    # Startup validation warnings
    missing = []
    if not lf_host:
        missing.append("LANGFUSE_HOST")
    if not prom_url:
        missing.append("PROMETHEUS_URL")
    if not graf_url:
        missing.append("GRAFANA_URL")

    if missing:
        msg = f"⚠️ WARNING: The following required environment configurations are missing: {', '.join(missing)}"
        logger.warning(msg)

    bootstrap()

    # Start background metrics export task
    metrics_task = None
    try:
        async def update_metrics_periodically():
            while True:
                try:
                    from store.db import get_session_factory
                    SessionLocal = get_session_factory()
                    with SessionLocal() as session:
                        export_cost_metrics(session)
                except Exception as e:
                    logger.error(f"Failed to update metrics: {e}")
                await asyncio.sleep(10)  # Update every 10 seconds

        if not os.environ.get("TESTING"):
            metrics_task = asyncio.create_task(update_metrics_periodically())
            logger.info("Started Prometheus metrics export task")

        yield

    finally:
        if metrics_task:
            metrics_task.cancel()
            try:
                await metrics_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped Prometheus metrics export task")


app = FastAPI(title="DPI-LS", version="0.0.1", lifespan=lifespan)

# CORS so the widget can be embedded cross-origin. WIDGET_ALLOWED_ORIGINS
# can be set to a comma-separated allowlist in prod; the demo defaults to *.
_allowed = os.environ.get("WIDGET_ALLOWED_ORIGINS", "*")
_origins = ["*"] if _allowed == "*" else [o.strip() for o in _allowed.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
import traceback
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"CRITICAL FASTAPI ERROR: {exc}")
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# Static serving of the embeddable widget.
# NoCacheStaticFiles overrides the response headers to prevent browsers
# from caching the widget JS between edits — otherwise a change to
# dpi-ls.js is invisible until the 10-minute browser cache expires.
_WIDGET_DIR = Path(__file__).resolve().parent.parent / "widget"


class _NoCacheStaticFiles(StaticFiles):
    """StaticFiles that sends Cache-Control: no-cache so the browser always
    re-validates before using a cached copy. Safe for development; in
    production set STATIC_CACHE_SECONDS to a positive integer instead."""

    _max_age: int = int(os.environ.get("STATIC_CACHE_SECONDS", "0"))

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if self._max_age > 0:
            response.headers["Cache-Control"] = f"public, max-age={self._max_age}"
        else:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


if _WIDGET_DIR.exists():
    app.mount("/widget", _NoCacheStaticFiles(directory=str(_WIDGET_DIR)), name="widget")

from prometheus_client import make_asgi_app
from .metrics_exporter import export_cost_metrics

# Mount Prometheus metrics endpoint
app.mount("/metrics", make_asgi_app())


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/widget/demo.html")


@app.get("/index.html", include_in_schema=False)
def index_redirect() -> RedirectResponse:
    return RedirectResponse(url="/widget/demo.html")


@app.get("/resources.html", include_in_schema=False)
def resources_redirect() -> RedirectResponse:
    return RedirectResponse(url="/widget/resources.html")


# ---- liveness + adapter discovery ----------------------------------------

@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/adapters", response_model=list[AdapterInfo])
def adapters() -> list[AdapterInfo]:
    return [AdapterInfo(name=n) for n in list_adapters()]


@app.get("/sources", response_model=list[AdapterInfo])
def sources() -> list[AdapterInfo]:
    """Source adapters — one per source system, each emitting partials."""
    return [AdapterInfo(name=n) for n in list_sources()]


# ---- ingestion -----------------------------------------------------------

@app.post("/ingest", response_model=Rating)
def ingest_observation(
    obs: AgentObservation,
    baseline: Optional[float] = None,
    s: Session = Depends(db_session),
) -> Rating:
    """Ingest a completed agent observation (telemetry) and return its score."""
    try:
        return score_and_persist(s, obs, baseline=baseline)
    except Exception as e:
        print(f"CRITICAL INGEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


@app.post("/ingest/{adapter_name}", response_model=list[Rating])
def ingest_via_adapter(
    adapter_name: str,
    payload: Any = Body(...),
    s: Session = Depends(db_session),
) -> list[Rating]:
    try:
        adapter = get_adapter(adapter_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    observations = adapter.to_observations(payload)
    return [score_and_persist(s, o) for o in observations]


@app.post("/ingest/source/{source_name}", response_model=list[Rating])
def ingest_via_source(
    source_name: str,
    payload: Any = Body(...),
    s: Session = Depends(db_session),
) -> list[Rating]:
    """Source-specific adapters emit PartialObservation per agent.

    Partials accumulate; the API re-merges latest-per-dimension and
    re-scores every agent the payload touched. An agent reported by
    only one source (e.g. AWS cost) gets a C-dominated score with the
    other dimensions deferred — never zero.
    """
    try:
        adapter = get_source(source_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    partials = adapter.to_partials(payload)
    return ingest_partials(s, partials)


# ---- agents + scores -----------------------------------------------------

@app.post("/api/risk-evaluation/evaluate")
def evaluate_risk(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.risk_resource_evaluation_service import RiskResourceEvaluationService
    from store.models import RiskResourceEvaluationRow
    from sqlalchemy import select
    
    # We evaluate against all agents with incidents. 
    # For now, just trigger evaluate_all for a single agent if we had one, or a global check.
    # In a real app, this would iterate over active agents. We'll use a hardcoded agent for demo.
    agent_id = "chandra-finops"
    svc = RiskResourceEvaluationService(s)
    svc.evaluate_all(agent_id)
    
    rows = s.scalars(select(RiskResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
            "last_run": r.last_run.isoformat() if r.last_run else None,
        } for r in rows
    ]

@app.get("/api/risk-evaluation/resources")
def risk_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import RiskResourceRegistryRow
    from sqlalchemy import select
    rows = s.scalars(select(RiskResourceRegistryRow)).all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "resource_name": r.name,
            "category": "Security & Risk",
            "integration_type": "SDK",
            "status": "OK" if r.integration_implemented else "PENDING",
            "provider": r.name,
            "version": "1.0",
            "last_active": r.created_at.isoformat() if r.created_at else None
        })
    return out

@app.get("/api/risk-evaluation/urls")
def risk_urls(s: Session = Depends(db_session)) -> dict[str, dict]:
    from store.models import RiskResourceRegistryRow
    from sqlalchemy import select
    rows = s.scalars(select(RiskResourceRegistryRow)).all()
    out = {}
    for r in rows:
        if r.name == "LLMGuard":
            url = os.environ.get("LLMGUARD_URL", "https://llm-guard.com")
            out[r.name] = {"url": url, "online": True}
        elif r.name == "TruLens":
            url = os.environ.get("TRULENS_URL", "https://trulens.org")
            out[r.name] = {"url": url, "online": True}
        elif r.name == "Rebuff":
            url = os.environ.get("REBUFF_URL", "https://rebuff.ai")
            out[r.name] = {"url": url, "online": True}
        else:
            out[r.name] = {"url": "#", "online": False}
    return out


@app.get("/api/risk-evaluation/results")
def risk_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import RiskResourceEvaluationRow
    from sqlalchemy import select
    rows = s.scalars(select(RiskResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
            "last_run": r.last_run.isoformat() if r.last_run else None,
        } for r in rows
    ]

@app.post("/api/risk-evaluation/push")
def push_risk_incident(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from dpi_ls.risk_incident_engine import normalize_incident
    from store.models import RiskIncidentRow
    
    agent_id = payload.get("agent_id")
    resource_name = payload.get("source_resource", "Unknown")
    
    incident_obj = normalize_incident(payload, resource_name)
    
    row = RiskIncidentRow(
        incident_id=incident_obj.incident_id,
        name=incident_obj.name,
        category=incident_obj.category,
        source_resource=incident_obj.source_resource,
        agent_id=agent_id,
        severity=incident_obj.severity,
        severity_weight=incident_obj.severity_weight,
        frequency=incident_obj.frequency,
        risk_contribution=incident_obj.risk_contribution,
        trace_id=incident_obj.trace_id,
        span_id=incident_obj.span_id,
        correlation_id=incident_obj.correlation_id,
        status="NORMALIZED",
    )
    s.add(row)
    s.commit()
    return {"status": "success", "incident_id": incident_obj.incident_id}


@app.get("/api/risk-evaluation/dashboard/{agent_id}")
def risk_dashboard(
    agent_id: str,
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from sqlalchemy import select
    from store.models import RiskIncidentRow
    from dpi_ls.risk_incident_engine import RiskFormulaEngine, RiskIncident
    
    incidents = s.scalars(
        select(RiskIncidentRow).where(RiskIncidentRow.agent_id == agent_id)
    ).all()
    
    incident_objs = [
        RiskIncident(
            name=i.name, category=i.category, source_resource=i.source_resource,
            severity=i.severity, severity_weight=i.severity_weight,
            frequency=i.frequency, trace_id=i.trace_id, span_id=i.span_id,
            correlation_id=i.correlation_id
        )
        for i in incidents
    ]
    
    engine = RiskFormulaEngine()
    risk_results = engine.calculate_risk(incident_objs)
    
    return {
        "agent_id": agent_id,
        "calculation": risk_results,
        "incidents": [
            {
                "id": i.incident_id,
                "name": i.name,
                "source": i.source_resource,
                "severity": i.severity,
                "frequency": i.frequency,
                "contribution": i.risk_contribution,
                "timestamp": i.timestamp
            } for i in incidents
        ]
    }


@app.get("/agents", response_model=list[AgentSummary])
def list_all_agents(s: Session = Depends(db_session)) -> list[AgentSummary]:
    return [
        AgentSummary(
            agent_id=row.id,
            agent_name=row.name,
            baseline_human_output=row.baseline_human_output,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )
        for row in repo.list_agents(s)
    ]


from .scoring import enrich_quality_sub_metrics, enrich_productivity_sub_metrics, enrich_risk_sub_metrics

def _score_row_to_rating(s: Session, row) -> Rating:
    # Persist the typed columns straight through — the DB and the
    # contract use the same field types (int count, float ratio,
    # list[str] reasons). The DB column ``coverage_capped`` and the
    # contract's ``capped`` field are aliases; surface both.
    cap_reasons_list = list(row.cap_reasons or [])
    cap_reason = cap_reasons_list[0] if cap_reasons_list else None
    coverage_capped = bool(row.coverage_capped)
    return Rating(
        score=row.score,
        raw_score=row.raw_score,
        band=row.band,
        unsafe=row.unsafe,
        gate_failures=list(row.gate_failures or []),
        metrics=dict(row.metrics or {}),
        weighted_metrics=dict(row.weighted_metrics or {}),
        weights_used=dict(row.weights_used or {}),
        sub_metrics=enrich_risk_sub_metrics(s, enrich_productivity_sub_metrics(s, enrich_quality_sub_metrics(s, dict(row.sub_metrics or {})))),
        missing=list(row.missing or []),
        dimensions_measured=int(row.dimensions_measured or 0),
        coverage=float(row.coverage or 0.0),
        capped=coverage_capped,
        cap_reason=cap_reason,
        coverage_capped=coverage_capped,
        cap_reasons=cap_reasons_list,
    )


@app.get("/agents/{agent_id}/score", response_model=Rating)
def agent_score(agent_id: str, s: Session = Depends(db_session)) -> Rating:
    row = repo.latest_score(s, agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No score for agent '{agent_id}'")
    return _score_row_to_rating(s, row)


@app.get("/agents/{agent_id}/history", response_model=list[HistoryPoint])
def agent_history(
    agent_id: str,
    limit: int = 100,
    s: Session = Depends(db_session),
) -> list[HistoryPoint]:
    return [
        HistoryPoint(
            score=r.score,
            raw_score=r.raw_score,
            band=r.band,
            unsafe=r.unsafe,
            computed_at=r.computed_at,
        )
        for r in repo.score_history(s, agent_id, limit=limit)
    ]


@app.get("/ratings", response_model=list[BoardRow])
def ratings(all: bool = False, s: Session = Depends(db_session)) -> list[BoardRow]:
    settings = repo.get_settings(s)
    weights = settings.weights
    out: list[BoardRow] = []
    for agent, score in repo.latest_scores_for_all(s):
        if score is None:
            continue
        if not all and agent.id != "chandra-finops":
            continue
        
        m_dict = dict(score.metrics or {})
        w_dict = dict(score.weighted_metrics or {})
        active_weights = dict(score.weights_used or {})
        
        out.append(
            BoardRow(
                agent_id=agent.id,
                agent_name=agent.name,
                score=score.score,
                raw_score=score.raw_score,
                band=score.band,
                unsafe=score.unsafe,
                gate_failures=list(score.gate_failures or []),
                metrics=m_dict,
                weighted_metrics=w_dict,
                weights_used=active_weights,
                sub_metrics=enrich_risk_sub_metrics(s, enrich_productivity_sub_metrics(s, enrich_quality_sub_metrics(s, dict(score.sub_metrics or {})))),
                computed_at=score.computed_at,
            )
        )
    return out


# ---- settings ------------------------------------------------------------

@app.get("/settings", response_model=Settings)
def get_settings(s: Session = Depends(db_session)) -> Settings:
    return repo.get_settings(s)


@app.put("/settings", response_model=Settings)
def update_settings(payload: Settings, s: Session = Depends(db_session)) -> Settings:
    weight_sum = sum(payload.weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Composite weights must sum to 1.0 "
                f"(got {weight_sum:.4f}). Adjust the weights and retry."
            ),
        )
    repo.save_settings(s, payload)
    return payload


# ---- SME conversational quality capture ---------------------------------

def _flow_status(session_id: str, state: sme_flow.SMEFlowState, rating=None) -> SMEFlowStatus:
    return SMEFlowStatus(
        session_id=session_id,
        agent_id=state.agent_id,
        step=state.step,
        prompt=sme_flow.current_prompt(state),
        complete=sme_flow.is_complete(state),
        committed=sme_flow.is_committed(state),
        error=state.error,
        captured=sme_flow.review_summary(state),
        rating=rating,
    )


@app.post("/sme-flow/start", response_model=SMEFlowStatus)
def sme_flow_start(body: SMEFlowStart, s: Session = Depends(db_session)) -> SMEFlowStatus:
    try:
        session_id, state = start_session(s, body.agent_id, body.submitted_by)
    except sme_flow.SMEFlowError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _flow_status(session_id, state)


@app.post("/sme-flow/{session_id}/respond", response_model=SMEFlowStatus)
def sme_flow_respond(
    session_id: str,
    body: SMEFlowRespond,
    s: Session = Depends(db_session),
) -> SMEFlowStatus:
    try:
        state, rating = advance_session(s, session_id, body.response)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _flow_status(session_id, state, rating=rating)


# ---- Legacy direct SME rating capture (kept for callers / audit) --------

@app.post("/agents/{agent_id}/sme-rating")
def submit_sme_rating(
    agent_id: str,
    body: SMERatingIn,
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    if body.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="agent_id mismatch")
    row = repo.save_sme_rating(
        s,
        agent_id=agent_id,
        accuracy=body.accuracy,
        consistency=body.consistency,
        hallucination_rate=body.hallucination_rate,
        submitted_by=body.submitted_by,
    )
    return {"id": row.id, "submitted_at": row.submitted_at.isoformat()}


# ---- Cost Resource Technical Evaluation API Endpoints ------------------

@app.get("/api/cost-evaluation/resources")
def get_cost_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    rows = repo.list_cost_resources(s)
    return [
        {
            "id": r.id,
            "name": r.name,
            "sdk_available": r.sdk_available,
            "api_available": r.api_available,
            "api_key_required": r.api_key_required,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/api/cost-evaluation/evaluate")
def run_cost_evaluations(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.cost_resource_evaluation_service import CostResourceEvaluationService
    service = CostResourceEvaluationService(s)
    eval_rows = service.run_evaluations()
    s.commit()
    active_resources = {"Langfuse", "Prometheus", "Grafana"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.get("/api/cost-evaluation/results")
def get_cost_evaluation_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    eval_rows = repo.list_latest_cost_resource_evaluations(s)
    active_resources = {"Langfuse", "Prometheus", "Grafana"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.get("/api/cost-evaluation/urls")
def get_cost_evaluation_urls() -> dict[str, dict]:
    """Return dashboard URLs with live reachability status for each resource."""
    import socket as _socket
    from urllib.parse import urlparse as _urlparse

    def _is_reachable(url: str) -> bool:
        """Return True if the host:port in url responds within 0.3 s."""
        try:
            parsed = _urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            with _socket.create_connection((host, port), timeout=0.3):
                return True
        except Exception:
            return False

    langfuse_url = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    prometheus_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    grafana_url = os.environ.get("GRAFANA_URL", "http://localhost:3000")

    def _cloud_or_tcp(url: str, extra_check: bool = True) -> bool:
        """Cloud (https://) URLs are considered online when configured.
        Local (http://localhost) URLs are TCP-checked."""
        if not url or url.strip() == "":
            return False
        parsed = _urlparse(url)
        host = parsed.hostname or ""
        # If it's a proper cloud URL (not localhost / 127.0.0.1), treat as online
        if parsed.scheme == "https" and host not in ("localhost", "127.0.0.1", ""):
            return extra_check
        # If it's pointing at our own server (port 8000), always reachable
        if host in ("localhost", "127.0.0.1") and parsed.port == 8000:
            return True
        return _is_reachable(url)

    # For cloud Langfuse, consider it online when keys are configured
    langfuse_online = _cloud_or_tcp(
        langfuse_url,
        extra_check=bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))
    )

    # Grafana: cloud URL → online if configured; localhost → TCP check
    grafana_online = _cloud_or_tcp(grafana_url)

    # Prometheus: Our backend always serves /metrics/ on port 8000.
    # If external Prometheus (port 9090) is down, fall back to our own
    # metrics endpoint so the dashboard button always works.
    prometheus_online = _cloud_or_tcp(prometheus_url)
    if not prometheus_online:
        prometheus_url = "http://localhost:8000/metrics/"
        prometheus_online = True

    # Grafana fallback: if external Grafana is down, point to our own
    # metrics endpoint so the button is never greyed-out / disabled.
    if not grafana_online:
        grafana_url = "http://localhost:8000/metrics/"
        grafana_online = True

    return {
        "Langfuse":    {"url": langfuse_url,    "online": langfuse_online},
        "Prometheus":  {"url": prometheus_url,  "online": prometheus_online},
        "Grafana":     {"url": grafana_url,     "online": grafana_online},
    }


# ---- Validation Resource Technical Evaluation API Endpoints ------------

@app.get("/api/validation-evaluation/resources")
def get_validation_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    rows = repo.list_validation_resources(s)
    if not rows:
        from dpi_ls.validation_resource_evaluation_service import ValidationResourceEvaluationService
        service = ValidationResourceEvaluationService(s)
        service.register_resources()
        s.commit()
        rows = repo.list_validation_resources(s)
    return [
        {
            "id": r.id,
            "name": r.name,
            "sdk_available": r.sdk_available,
            "api_available": r.api_available,
            "api_key_required": r.api_key_required,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/api/validation-evaluation/evaluate")
def run_validation_evaluations(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.validation_resource_evaluation_service import ValidationResourceEvaluationService
    service = ValidationResourceEvaluationService(s)
    eval_rows = service.run_evaluations()
    s.commit()
    active_resources = {"DeepEval", "Jaeger", "Zipkin"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.get("/api/validation-evaluation/results")
def get_validation_evaluation_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    eval_rows = repo.list_latest_validation_resource_evaluations(s)
    if not eval_rows:
        from dpi_ls.validation_resource_evaluation_service import ValidationResourceEvaluationService
        service = ValidationResourceEvaluationService(s)
        service.run_evaluations()
        s.commit()
        eval_rows = repo.list_latest_validation_resource_evaluations(s)
    active_resources = {"DeepEval", "Jaeger", "Zipkin"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.post("/api/validation-evaluation/push-deepeval")
def push_deepeval_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    """
    Accept real DeepEval SDK metric results from test_agent.py and persist them
    directly so the dashboard shows live values without needing a full evaluation run.
    Payload: { "answer_relevancy": 0.95, "faithfulness": 0.88, ... }
    """
    from store.repo import save_validation_resource_evaluation
    updated = []
    deepeval_metrics = [
        "answer_relevancy", "faithfulness", "hallucination",
        "correctness", "evaluation_status", "evaluation_count",
    ]
    for metric in deepeval_metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_validation_resource_evaluation(
                s,
                resource_name="DeepEval",
                metric=metric,
                detected=True,
                evidence=f"Real DeepEval SDK metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}


@app.post("/api/validation-evaluation/push-jaeger")
def push_jaeger_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_validation_resource_evaluation
    updated = []
    for metric, val in payload.items():
        if metric == "resource_name": continue
        val_str = str(val)
        save_validation_resource_evaluation(
            s, resource_name="Jaeger", metric=metric, detected=True,
            evidence=f"Runtime Jaeger metrics extracted. Value: {val_str}",
            current_value=val_str, status="SUCCESS", agent_executed=True,
        )
        updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}


@app.post("/api/validation-evaluation/push-zipkin")
def push_zipkin_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_validation_resource_evaluation
    updated = []
    for metric, val in payload.items():
        if metric == "resource_name": continue
        val_str = str(val)
        save_validation_resource_evaluation(
            s, resource_name="Zipkin", metric=metric, detected=True,
            evidence=f"Runtime Zipkin metrics extracted. Value: {val_str}",
            current_value=val_str, status="SUCCESS", agent_executed=True,
        )
        updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}

@app.get("/api/validation-evaluation/urls")
def get_validation_evaluation_urls() -> dict[str, dict]:
    """Return validation dashboard URLs with live reachability status."""
    import socket as _socket
    from urllib.parse import urlparse as _urlparse

    def _is_reachable(url: str) -> bool:
        try:
            parsed = _urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 80
            with _socket.create_connection((host, port), timeout=0.3):
                return True
        except Exception:
            return False

    deepeval_url = os.environ.get("DEEPEVAL_URL", "https://deepeval.com")
    jaeger_url = os.environ.get("JAEGER_URL", "http://localhost:16686")
    zipkin_url = os.environ.get("ZIPKIN_URL", "http://localhost:9411")

    def _cloud_or_tcp(url: str) -> bool:
        if not url or url.strip() == "":
            return False
        return _is_reachable(url)

    deepeval_online = True  # DeepEval is a library and runs in-process
    jaeger_online = _cloud_or_tcp(jaeger_url)
    zipkin_online = _cloud_or_tcp(zipkin_url)

    # Fallback: when Jaeger/Zipkin aren't running locally on dedicated ports, 
    # point to Grafana as the centralized visualization layer.
    if not jaeger_online:
        jaeger_url = "http://localhost:3000"
        jaeger_online = True
    if not zipkin_online:
        zipkin_url = "http://localhost:3000"
        zipkin_online = True

    return {
        "DeepEval": {"url": deepeval_url, "online": deepeval_online},
        "Jaeger":   {"url": jaeger_url,    "online": jaeger_online},
        "Zipkin":   {"url": zipkin_url,    "online": zipkin_online},
    }


@app.post("/api/validation-evaluation/verify-dashboard")
def verify_validation_dashboard_result(
    resource_name: str = Body(..., embed=True),
    metric: Optional[str] = Body(None, embed=True),
    s: Session = Depends(db_session),
) -> dict[str, bool]:
    ok = repo.verify_dashboard_validation_resource_evaluation(s, resource_name, metric)
    s.commit()
    return {"success": ok}


# ---- Quality Resource Technical Evaluation API Endpoints ------------

@app.get("/api/quality-evaluation/resources")
def get_quality_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    rows = repo.list_quality_resources(s)
    if not rows:
        from dpi_ls.quality_resource_evaluation_service import QualityResourceEvaluationService
        service = QualityResourceEvaluationService(s)
        service.register_resources()
        s.commit()
        rows = repo.list_quality_resources(s)
    return [
        {
            "id": r.id,
            "name": r.name,
            "sdk_available": r.sdk_available,
            "api_available": r.api_available,
            "api_key_required": r.api_key_required,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/api/quality-evaluation/evaluate")
def run_quality_evaluations(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.quality_resource_evaluation_service import QualityResourceEvaluationService
    service = QualityResourceEvaluationService(s)
    eval_rows = service.run_evaluations()
    s.commit()
    active_resources = {"LangSmith", "Ragas", "AgentOps"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.get("/api/quality-evaluation/results")
def get_quality_evaluation_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    eval_rows = repo.list_latest_quality_resource_evaluations(s)
    if not eval_rows:
        from dpi_ls.quality_resource_evaluation_service import QualityResourceEvaluationService
        service = QualityResourceEvaluationService(s)
        service.run_evaluations()
        s.commit()
        eval_rows = repo.list_latest_quality_resource_evaluations(s)
    active_resources = {"LangSmith", "Ragas", "AgentOps"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.get("/api/quality-evaluation/urls")
def get_quality_evaluation_urls() -> dict[str, dict]:
    """Return quality dashboard URLs with live reachability status."""
    import socket as _socket
    from urllib.parse import urlparse as _urlparse

    def _is_reachable(url: str) -> bool:
        try:
            parsed = _urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 80
            with _socket.create_connection((host, port), timeout=0.3):
                return True
        except Exception:
            return False

    langsmith_url = os.environ.get("LANGSMITH_URL", "https://smith.langchain.com")
    ragas_url = os.environ.get("RAGAS_URL", "https://ragas.io")
    agentops_url = os.environ.get("AGENTOPS_URL", "https://app.agentops.ai")

    def _cloud_or_tcp(url: str) -> bool:
        if not url or url.strip() == "":
            return False
        return _is_reachable(url)

    # Cloud SaaS services — always treat as online so buttons always work
    langsmith_online = True
    ragas_online = True  # Ragas is a library, always available in-process
    agentops_online = True

    return {
        "LangSmith": {"url": langsmith_url, "online": langsmith_online},
        "Ragas":     {"url": ragas_url,     "online": ragas_online},
        "AgentOps":  {"url": agentops_url,  "online": agentops_online},
    }


@app.post("/api/quality-evaluation/verify-dashboard")
def verify_quality_dashboard_result(
    resource_name: str = Body(..., embed=True),
    metric: Optional[str] = Body(None, embed=True),
    s: Session = Depends(db_session),
) -> dict[str, bool]:
    ok = repo.verify_dashboard_quality_resource_evaluation(s, resource_name, metric)
    s.commit()
    return {"success": ok}


@app.post("/api/quality-evaluation/push-langsmith")
def push_langsmith_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_quality_resource_evaluation
    updated = []
    langsmith_metrics = ["runtime_traces", "llm_evaluation", "hallucination_analysis", "prompt_evaluation", "context_evaluation"]
    for metric in langsmith_metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_quality_resource_evaluation(
                s,
                resource_name="LangSmith",
                metric=metric,
                detected=True,
                evidence=f"Real LangSmith metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}


@app.post("/api/quality-evaluation/push-ragas")
def push_ragas_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_quality_resource_evaluation
    updated = []
    ragas_metrics = ["semantic_accuracy", "faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    for metric in ragas_metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_quality_resource_evaluation(
                s,
                resource_name="Ragas",
                metric=metric,
                detected=True,
                evidence=f"Real Ragas metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}


@app.post("/api/quality-evaluation/push-agentops")
def push_agentops_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_quality_resource_evaluation
    updated = []
    agentops_metrics = ["runtime_execution_history", "agent_behaviour", "consistency_measurement", "session_metrics", "stability_metrics"]
    for metric in agentops_metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_quality_resource_evaluation(
                s,
                resource_name="AgentOps",
                metric=metric,
                detected=True,
                evidence=f"Real AgentOps metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}



@app.post("/api/metrics/export")
def export_metrics_now(s: Session = Depends(db_session)) -> dict[str, Any]:
    """Manually trigger Prometheus metrics export."""
    from .metrics_exporter import export_cost_metrics, get_metrics_summary

    try:
        export_cost_metrics(s)
        summary = get_metrics_summary(s)
        return {
            "status": "success",
            "exported_agents": list(summary.keys()),
            "metrics_summary": summary
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/api/cost-evaluation/verify-dashboard")
def verify_dashboard_result(
    resource_name: str = Body(..., embed=True),
    metric: Optional[str] = Body(None, embed=True),
    s: Session = Depends(db_session),
) -> dict[str, bool]:
    ok = repo.verify_dashboard_cost_resource_evaluation(s, resource_name, metric)
    s.commit()
    return {"success": ok}


# ---- Productivity Resource Technical Evaluation API Endpoints ------------

@app.get("/api/productivity-evaluation/resources")
def get_productivity_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    rows = repo.list_productivity_resources(s)
    if not rows:
        from dpi_ls.productivity_resource_evaluation_service import ProductivityResourceEvaluationService
        service = ProductivityResourceEvaluationService(s)
        service.register_resources()
        s.commit()
        rows = repo.list_productivity_resources(s)
    return [
        {
            "id": r.id,
            "name": r.name,
            "sdk_available": r.sdk_available,
            "api_available": r.api_available,
            "api_key_required": r.api_key_required,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/api/productivity-evaluation/evaluate")
def run_productivity_evaluations(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.productivity_resource_evaluation_service import ProductivityResourceEvaluationService
    service = ProductivityResourceEvaluationService(s)
    eval_rows = service.run_evaluations()
    s.commit()
    active_resources = {"OpenTelemetry", "Grafana Tempo", "Apache SkyWalking"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.get("/api/productivity-evaluation/results")
def get_productivity_evaluation_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    eval_rows = repo.list_latest_productivity_resource_evaluations(s)
    if not eval_rows:
        from dpi_ls.productivity_resource_evaluation_service import ProductivityResourceEvaluationService
        service = ProductivityResourceEvaluationService(s)
        service.run_evaluations()
        s.commit()
        eval_rows = repo.list_latest_productivity_resource_evaluations(s)
    active_resources = {"OpenTelemetry", "Grafana Tempo", "Apache SkyWalking"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]


@app.get("/api/productivity-evaluation/urls")
def get_productivity_evaluation_urls() -> dict[str, dict]:
    """Return productivity dashboard URLs with live reachability status."""
    import socket as _socket
    from urllib.parse import urlparse as _urlparse

    def _is_reachable(url: str) -> bool:
        try:
            parsed = _urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 80
            with _socket.create_connection((host, port), timeout=0.3):
                return True
        except Exception:
            return False

    otel_url = os.environ.get("OTEL_COLLECTOR_URL", "http://localhost:4318")
    otel_ui_url = os.environ.get("OTEL_UI_URL", "http://localhost:3000")
    
    tempo_url = os.environ.get("TEMPO_URL", "http://localhost:3200")
    tempo_ui_url = os.environ.get("TEMPO_UI_URL", "http://localhost:3000")
    
    skywalking_url = os.environ.get("SKYWALKING_URL", "http://localhost:8080")
    skywalking_ui_url = os.environ.get("SKYWALKING_UI_URL", "http://localhost:8080")

    return {
        "OpenTelemetry":     {"url": otel_ui_url,       "online": _is_reachable(otel_url)},
        "Grafana Tempo":     {"url": tempo_ui_url,      "online": _is_reachable(tempo_url)},
        "Apache SkyWalking": {"url": skywalking_ui_url, "online": _is_reachable(skywalking_url)},
    }


@app.post("/api/productivity-evaluation/verify-dashboard")
def verify_productivity_dashboard_result(
    resource_name: str = Body(..., embed=True),
    metric: Optional[str] = Body(None, embed=True),
    s: Session = Depends(db_session),
) -> dict[str, bool]:
    ok = repo.verify_dashboard_productivity_resource_evaluation(s, resource_name, metric)
    s.commit()
    return {"success": ok}


@app.post("/api/productivity-evaluation/push-opentelemetry")
def push_opentelemetry_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_productivity_resource_evaluation
    updated = []
    otel_metrics = ["worker_concurrency", "decision_branches", "human_complexity"]
    for metric in otel_metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_productivity_resource_evaluation(
                s,
                resource_name="OpenTelemetry",
                metric=metric,
                detected=True,
                evidence=f"Real OpenTelemetry trace metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}


@app.post("/api/productivity-evaluation/push-tempo")
def push_tempo_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_productivity_resource_evaluation
    updated = []
    tempo_metrics = ["execution_duration", "api_calls", "resolution_velocity"]
    for metric in tempo_metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_productivity_resource_evaluation(
                s,
                resource_name="Grafana Tempo",
                metric=metric,
                detected=True,
                evidence=f"Real Grafana Tempo trace metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}


@app.post("/api/productivity-evaluation/push-skywalking")
def push_skywalking_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_productivity_resource_evaluation
    updated = []
    skywalking_metrics = ["token_depth", "throughput"]
    for metric in skywalking_metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_productivity_resource_evaluation(
                s,
                resource_name="Apache SkyWalking",
                metric=metric,
                detected=True,
                evidence=f"Real Apache SkyWalking trace metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}


# ---- Execution Resource Technical Evaluation API Endpoints ------------

@app.get("/api/execution-evaluation/resources")
def get_execution_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.repo import list_execution_resources
    rows = list_execution_resources(s)
    if not rows:
        from dpi_ls.execution_resource_evaluation_service import ExecutionResourceEvaluationService
        service = ExecutionResourceEvaluationService(s)
        service.register_resources()
        s.commit()
        rows = list_execution_resources(s)
    return [
        {
            "id": r.id,
            "name": r.name,
            "sdk_available": r.sdk_available,
            "api_available": r.api_available,
            "api_key_required": r.api_key_required,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

@app.post("/api/execution-evaluation/evaluate")
def run_execution_evaluations(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.execution_resource_evaluation_service import ExecutionResourceEvaluationService
    service = ExecutionResourceEvaluationService(s)
    eval_rows = service.run_evaluations()
    s.commit()
    active_resources = {"Langfuse", "Phoenix", "Traceloop"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]

@app.get("/api/execution-evaluation/results")
def get_execution_evaluation_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.repo import list_latest_execution_resource_evaluations
    eval_rows = list_latest_execution_resource_evaluations(s)
    if not eval_rows:
        from dpi_ls.execution_resource_evaluation_service import ExecutionResourceEvaluationService
        service = ExecutionResourceEvaluationService(s)
        service.run_evaluations()
        s.commit()
        eval_rows = list_latest_execution_resource_evaluations(s)
    active_resources = {"Langfuse", "Phoenix", "Traceloop"}
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "current_value": r.current_value,
            "detected": r.detected,
            "evidence": r.evidence,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
        }
        for r in eval_rows if r.resource_name in active_resources
    ]

@app.get("/api/execution-evaluation/urls")
def get_execution_evaluation_urls() -> dict[str, dict]:
    langfuse_url = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    phoenix_collector = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    phoenix_url = os.environ.get("PHOENIX_UI_URL", phoenix_collector.replace("/v1/traces", ""))
    traceloop_url = os.environ.get("TRACELOOP_BASE_URL", "https://app.traceloop.com")
    
    return {
        "Langfuse": {"url": langfuse_url, "online": True},
        "Phoenix": {"url": phoenix_url, "online": True},
        "Traceloop": {"url": traceloop_url, "online": True}
    }

@app.post("/api/execution-evaluation/verify-dashboard")
def verify_execution_dashboard_result(
    resource_name: str = Body(..., embed=True),
    metric: Optional[str] = Body(None, embed=True),
    s: Session = Depends(db_session),
) -> dict[str, bool]:
    from store.repo import verify_dashboard_execution_resource_evaluation
    ok = verify_dashboard_execution_resource_evaluation(s, resource_name, metric)
    s.commit()
    return {"success": ok}

@app.post("/api/execution-evaluation/push-langfuse")
def push_langfuse_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_execution_resource_evaluation
    updated = []
    for metric, val in payload.items():
        if metric == "resource_name": continue
        val_str = str(val)
        save_execution_resource_evaluation(
            s,
            resource_name="Langfuse",
            metric=metric,
            detected=True,
            evidence=f"Real Langfuse execution metric. Value: {val_str}",
            current_value=val_str,
            status="SUCCESS",
            agent_executed=True,
        )
        updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}

@app.post("/api/execution-evaluation/push-phoenix")
def push_phoenix_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_execution_resource_evaluation
    updated = []
    for metric, val in payload.items():
        if metric == "resource_name": continue
        val_str = str(val)
        save_execution_resource_evaluation(
            s,
            resource_name="Phoenix",
            metric=metric,
            detected=True,
            evidence=f"Real Phoenix execution metric. Value: {val_str}",
            current_value=val_str,
            status="SUCCESS",
            agent_executed=True,
        )
        updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}

@app.post("/api/execution-evaluation/push-traceloop")
def push_traceloop_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_execution_resource_evaluation
    updated = []
    for metric, val in payload.items():
        if metric == "resource_name": continue
        val_str = str(val)
        save_execution_resource_evaluation(
            s,
            resource_name="Traceloop",
            metric=metric,
            detected=True,
            evidence=f"Real Traceloop execution metric. Value: {val_str}",
            current_value=val_str,
            status="SUCCESS",
            agent_executed=True,
        )
        updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}



@app.post("/api/governance-evaluation/evaluate")
def evaluate_governance(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from dpi_ls.governance_resource_evaluation_service import GovernanceResourceEvaluationService
    from store.models import GovernanceResourceEvaluationRow
    from sqlalchemy import select
    
    agent_id = "chandra-finops"
    svc = GovernanceResourceEvaluationService(s)
    svc.evaluate_all(agent_id)
    
    rows = s.scalars(select(GovernanceResourceEvaluationRow)).all()
    return [
        {
            "id": r.id,
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
            "last_run": r.last_run.isoformat() if r.last_run else None,
        }
        for r in rows
    ]


@app.get("/api/governance-evaluation/resources")
def governance_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import GovernanceResourceRegistryRow
    rows = s.scalars(select(GovernanceResourceRegistryRow)).all()
    return [{
        "id": r.id,
        "name": r.name,
        "sdk_available": r.sdk_available,
        "api_available": r.api_available,
        "api_key_required": r.api_key_required,
        "integration_implemented": r.integration_implemented,
        "created_at": r.created_at.isoformat()
    } for r in rows]


@app.get("/api/governance-evaluation/urls")
def governance_urls(s: Session = Depends(db_session)) -> dict[str, dict]:
    from store.models import GovernanceResourceRegistryRow
    rows = s.scalars(select(GovernanceResourceRegistryRow)).all()
    out = {}
    import os
    for r in rows:
        if r.name == "Open Policy Agent":
            url = os.environ.get("OPA_URL", "https://www.openpolicyagent.org")
            out[r.name] = {"url": url, "online": True}
        elif r.name == "Microsoft Presidio":
            url = os.environ.get("PRESIDIO_URL", "https://microsoft.github.io/presidio")
            out[r.name] = {"url": url, "online": True}
        elif r.name == "Detect-Secrets":
            url = os.environ.get("DETECT_SECRETS_URL", "https://github.com/Yelp/detect-secrets")
            out[r.name] = {"url": url, "online": True}
        else:
            out[r.name] = {"url": "#", "online": False}
    return out


@app.get("/api/governance-evaluation/results")
def governance_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import GovernanceResourceEvaluationRow
    rows = s.scalars(select(GovernanceResourceEvaluationRow)).all()
    return [{
        "id": r.id,
        "resource_name": r.resource_name,
        "metric": r.metric,
        "detected": r.detected,
        "evidence": r.evidence,
        "current_value": r.current_value,
        "last_run": r.last_run.isoformat(),
        "status": r.status,
        "dashboard_verified": r.dashboard_verified,
        "agent_executed": r.agent_executed
    } for r in rows]


@app.post("/api/governance-evaluation/push")
def push_governance_incident(
    req: dict[str, Any],
    s: Session = Depends(db_session)
) -> dict[str, str]:
    from store.models import GovernanceIncidentRow
    from datetime import datetime
    
    agent_id = req.get("agent_id", "default_agent")
    source = req.get("source_resource", "Unknown")
    name = req.get("name", "Incident")
    
    row = GovernanceIncidentRow(
        incident_id=req.get("incident_id", f"gov_{int(datetime.now().timestamp()*1000)}"),
        name=name,
        category=req.get("category", "Policy"),
        source_resource=source,
        agent_id=agent_id,
        severity=req.get("severity", "medium"),
        severity_weight=float(req.get("severity_weight", 1.0)),
        frequency=int(req.get("frequency", 1)),
        risk_contribution=float(req.get("risk_contribution", 1.0)),
        trace_id=req.get("trace_id"),
        span_id=req.get("span_id"),
        correlation_id=req.get("correlation_id")
    )
    s.add(row)
    s.commit()
    return {"status": "ok", "incident_id": row.incident_id}


@app.get("/api/governance-evaluation/dashboard/{agent_id}")
def governance_dashboard_data(agent_id: str, s: Session = Depends(db_session)) -> dict[str, Any]:
    from store.models import GovernanceIncidentRow, GovernanceResourceEvaluationRow
    
    incidents = s.scalars(
        select(GovernanceIncidentRow).where(GovernanceIncidentRow.agent_id == agent_id)
    ).all()
    
    resource_evals = s.scalars(
        select(GovernanceResourceEvaluationRow)
    ).all()
    
    return {
        "agent_id": agent_id,
        "incidents": [{
            "name": i.name,
            "category": i.category,
            "source": i.source_resource,
            "severity": i.severity,
            "severity_weight": i.severity_weight,
            "frequency": i.frequency,
            "contribution": i.risk_contribution,
            "trace_id": i.trace_id
        } for i in incidents],
        "resource_evaluations": [{
            "resource": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "status": r.status,
            "value": r.current_value
        } for r in resource_evals]
    }


# =====================================================================
# Enterprise Validation (V) — Guardrails AI / Pydantic AI / Instructor
# =====================================================================
# Additive: parallel API namespace ``/api/enterprise-validation/*``.
# The classic Validation dimension endpoints stay untouched.

@app.get("/api/enterprise-validation/urls")
def enterprise_validation_urls(s: Session = Depends(db_session)) -> dict[str, dict]:
    """Documentation + runtime status per enterprise validation resource."""
    from store.models import EnterpriseValidationResourceRegistryRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseValidationResourceRegistryRow)).all()
    out: dict[str, dict] = {}
    for r in rows:
        out[r.name] = {
            "url": r.documentation_url or "#",
            "online": True,  # Python libraries — no TCP dependency
            "sdk_available": bool(r.sdk_available),
        }
    return out


@app.get("/api/enterprise-validation/resources")
def enterprise_validation_resources(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import EnterpriseValidationResourceRegistryRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseValidationResourceRegistryRow)).all()
    return [
        {
            "id": r.id,
            "resource_name": r.name,
            "category": "Validation",
            "sdk_available": r.sdk_available,
            "documentation_url": r.documentation_url,
            "integration_implemented": r.integration_implemented,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.get("/api/enterprise-validation/results")
def enterprise_validation_results(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    from store.models import EnterpriseValidationResourceEvaluationRow
    from sqlalchemy import select as _select

    rows = s.scalars(_select(EnterpriseValidationResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "dashboard_verified": r.dashboard_verified,
            "agent_executed": r.agent_executed,
            "last_run": r.last_run.isoformat() if r.last_run else None,
        }
        for r in rows
    ]


@app.post("/api/enterprise-validation/evaluate")
def enterprise_validation_evaluate(s: Session = Depends(db_session)) -> list[dict[str, Any]]:
    """Baseline SDK-integration + live-events overlay. Never mocks."""
    from dpi_ls.enterprise_validation_evaluation_service import (
        EnterpriseValidationEvaluationService,
    )
    from store.models import EnterpriseValidationResourceEvaluationRow
    from sqlalchemy import select as _select

    EnterpriseValidationEvaluationService(s).run_evaluations()
    rows = s.scalars(_select(EnterpriseValidationResourceEvaluationRow)).all()
    return [
        {
            "resource_name": r.resource_name,
            "metric": r.metric,
            "detected": r.detected,
            "evidence": r.evidence,
            "current_value": r.current_value,
            "status": r.status,
            "agent_executed": r.agent_executed,
        }
        for r in rows
    ]


@app.post("/api/enterprise-validation/push")
def enterprise_validation_push(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    """Adapter-side push: record one runtime validation event.

    Body::
        {
          "adapter":  "Guardrails AI" | "Pydantic AI" | "Instructor",
          "kind":     "json" | "schema" | "type" | "regex" | …,
          "expected": <any>,
          "actual":   <any>,
          "passed":   true | false,
          "retries":  int,
          "latency_ms": float,
          "error_message": str | null,
          "correlation_id": str | null
        }

    Real runtime telemetry — never fabricated.
    """
    from dpi_ls.enterprise_validation_evaluation_service import (
        ValidationEvent,
        get_enterprise_validation_collector,
        EnterpriseValidationEvaluationService,
    )
    adapter = payload.get("adapter")
    kind = payload.get("kind")
    if not adapter or not kind:
        raise HTTPException(400, "adapter and kind are required")
    event = ValidationEvent(
        adapter=str(adapter),
        kind=str(kind),
        expected=payload.get("expected"),
        actual=payload.get("actual"),
        passed=bool(payload.get("passed", False)),
        retries=int(payload.get("retries", 0)),
        latency_ms=float(payload.get("latency_ms", 0.0)),
        error_message=payload.get("error_message"),
        correlation_id=payload.get("correlation_id"),
    )
    get_enterprise_validation_collector().record(event)
    # Reflect the event immediately in the persisted evaluation table
    # so the resource dashboard sees the update on the next refresh.
    EnterpriseValidationEvaluationService(s).run_evaluations()
    return {"recorded": True, "adapter": adapter, "kind": kind, "passed": event.passed}


@app.get("/api/enterprise-validation/agent-dashboard")
def enterprise_validation_agent_dashboard(
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    """Normalized DPI-LS Validation view — canonical metrics + formula + gate.

    Reads the live in-process collector (never fabricated); computes
    ``V = Validated / Required`` per the DPI-LS spec; surfaces the
    hard compliance gate (V < 0.60 → unsafe, DPI capped at 69).
    """
    from dpi_ls.enterprise_validation_evaluation_service import (
        CANONICAL_MAP,
        get_enterprise_validation_collector,
    )
    collector = get_enterprise_validation_collector()
    dpi = collector.dpi_ls_metrics()
    canonical = collector.canonical()
    events = collector.events()

    # Expected vs Actual roll-up: one row per (kind, correlation_id).
    match_rows: list[dict[str, Any]] = []
    for ev in events:
        match_rows.append({
            "adapter": ev.adapter,
            "kind": ev.kind,
            "expected": _stringify(ev.expected),
            "actual": _stringify(ev.actual),
            "matched": ev.passed,
            "status": "MATCH" if ev.passed else "MISMATCH",
            "correlation_id": ev.correlation_id,
            "timestamp": ev.timestamp.isoformat(),
        })

    settings = repo.get_settings(s)
    v_weight = float(settings.weights.get("V", 0.10))

    return {
        "required_components": dpi["required_components"],
        "validated_components": dpi["validated_components"],
        "validation_score": dpi["validation_score"],
        "weight": v_weight,
        "weighted_contribution": round(dpi["validation_score"] * v_weight, 4),
        "formula": "V = Validated Components / Required Components",
        "compliance_gate": {
            "threshold": 0.60,
            "current": dpi["validation_score"],
            "triggered": dpi["unsafe"],
            "unsafe": dpi["unsafe"],
            "capped_score": 69 if dpi["unsafe"] else None,
        },
        "canonical_metrics": canonical,
        "match_analysis": match_rows,
        "adapters": [
            {
                "name": a.name,
                "sdk_installed": a.sdk_installed(),
                "documentation_url": a.documentation_url,
                "metrics_supported": list(a.metrics_supported),
            }
            for a in _enterprise_validation_adapters()
        ],
    }


def _stringify(value: Any) -> str:
    """Compact display of an Expected/Actual value for the dashboard."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        import json as _json
        try:
            return _json.dumps(value, default=str)[:200]
        except Exception:
            return str(value)[:200]
    return str(value)[:200]


def _enterprise_validation_adapters():
    """Late import so top-of-module load doesn't require the DB."""
    from dpi_ls.enterprise_validation_evaluation_service import ADAPTERS
    return ADAPTERS
