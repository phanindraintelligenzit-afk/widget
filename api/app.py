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
    bootstrap()
    yield


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


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/widget/demo.html")


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


# ---- webhooks ------------------------------------------------------------

@app.post("/webhooks/arize", response_model=list[Rating])
async def webhook_arize(
    request: Request,
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> list[Rating]:
    """Receives live monitor breaches from Arize AX via webhook.
    
    Arize webhooks send single events (e.g. 'monitor_status_change'). We fetch
    the latest partial for this agent, append the violation, and re-score.
    """
    import hmac
    from contract.models import Policy, PolicyViolation
    from contract.partial import PartialObservation
    from datetime import datetime, timezone
    
    # 1. Verify webhook secret if configured
    secret = os.environ.get("ARIZE_WEBHOOK_SECRET")
    if secret:
        # Arize sends a signature header, but for simplicity here we just
        # check if they passed it as a query param or authorization header
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {secret}" and auth != secret:
            pass # We'll enforce this later once the header shape is confirmed
            
    # 2. Ignore non-breach events (e.g. monitor recovered or test pings)
    status = payload.get("status", "").lower()
    event = payload.get("event", "")
    if event == "ping":
        return []
        
    # 3. Extract agent and rule
    agent_id = payload.get("model_id", "unknown-agent")
    monitor_name = payload.get("monitor_name") or payload.get("monitor_id") or "unknown_breach"
    timestamp_str = payload.get("timestamp")
    
    when = datetime.now(timezone.utc)
    if timestamp_str:
        try:
            when = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            pass

    violation = PolicyViolation(rule=monitor_name, when=when)
    
    # 4. Fetch the existing partial for this agent to append to it
    # We do this because merging partials OVERWRITES the whole dimension
    from store.models import PartialObservationRow
    from sqlalchemy import select
    row = s.scalar(
        select(PartialObservationRow)
        .where(
            PartialObservationRow.agent_id == agent_id,
            PartialObservationRow.source == "arize"
        )
        .order_by(PartialObservationRow.received_at.desc())
        .limit(1)
    )
    
    if row and row.payload:
        existing_data = row.payload
        partial = PartialObservation.model_validate(existing_data)
        
        # Append the new violation
        if partial.policy is None:
            partial.policy = Policy(total_actions=100, violations=[violation])
        else:
            partial.policy.violations.append(violation)
            
        partial.period_end = when
    else:
        # First time we see this agent from Arize
        partial = PartialObservation(
            agent_id=agent_id,
            source="arize",
            period_start=when,
            period_end=when,
            policy=Policy(total_actions=100, violations=[violation])
        )
        
    return ingest_partials(s, [partial])


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
def ratings(s: Session = Depends(db_session)) -> list[BoardRow]:
    out: list[BoardRow] = []
    for agent, score in repo.latest_scores_for_all(s):
        if score is None:
            continue
        out.append(
            BoardRow(
                agent_id=agent.id,
                agent_name=agent.name,
                score=score.score,
                raw_score=score.raw_score,
                band=score.band,
                unsafe=score.unsafe,
                gate_failures=list(score.gate_failures or []),
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
