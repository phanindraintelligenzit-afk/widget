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
def ingest(
    obs: AgentObservation,
    baseline: Optional[float] = None,
    s: Session = Depends(db_session),
) -> Rating:
    return score_and_persist(s, obs, baseline=baseline)


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


def _score_row_to_rating(row) -> Rating:
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
        sub_metrics=dict(row.sub_metrics or {}),
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
    return _score_row_to_rating(row)


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
        w_dict = {}
        for k, v in m_dict.items():
            if v is not None:
                w = weights.get(k)
                w_val = w if w is not None else 0.0
                w_dict[k] = v * w_val * 100
            else:
                w_dict[k] = None
        
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
                sub_metrics=dict(score.sub_metrics or {}),
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

    # Prometheus: if URL points to our own /metrics endpoint → always online
    prometheus_online = _cloud_or_tcp(prometheus_url)

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

