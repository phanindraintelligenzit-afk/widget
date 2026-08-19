import pytest
from dpi_ls.trace import ScoreTrace
from store.models import ScoreTraceRow
from store.db import get_session_factory, init_db

def test_trace_recomputation_matches_final_score():
    # If there are any traces, verify their math
    init_db()
    sf = get_session_factory()
    with sf() as s:
        traces = s.query(ScoreTraceRow).all()
        for row in traces:
            trace = row.trace
            agg = trace.get("aggregation", {})
            term1 = agg.get("term1", 0.0)
            term2 = agg.get("term2", 0.0)
            term3 = agg.get("term3", 0.0)
            pre_band_score = (term1 + term2 + term3) * 25.0
            
            assert abs(round(pre_band_score, 2) - row.final_score) < 1e-9, f"Trace math failed for {row.run_id}"

def test_missing_trace_returns_404():
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    response = client.get("/trace/fake-run-id")
    assert response.status_code == 404
