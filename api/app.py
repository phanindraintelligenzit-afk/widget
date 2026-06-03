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
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException
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
_WIDGET_DIR = Path(__file__).resolve().parent.parent / "widget"
if _WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(_WIDGET_DIR)), name="widget")


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
def ingest(obs: AgentObservation, s: Session = Depends(db_session)) -> Rating:
    return score_and_persist(s, obs)


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
    return Rating(
        score=row.score,
        raw_score=row.raw_score,
        band=row.band,
        unsafe=row.unsafe,
        gate_failures=list(row.gate_failures or []),
        metrics=dict(row.metrics or {}),
        missing=list(row.missing or []),
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
                band=score.band,
                unsafe=score.unsafe,
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
