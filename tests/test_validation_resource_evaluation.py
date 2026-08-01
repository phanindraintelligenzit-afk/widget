import os
from sqlalchemy import select
from store.db import get_session_factory
from store.models import ValidationResourceRegistryRow, ValidationResourceEvaluationRow
from dpi_ls.validation_resource_evaluation_service import ValidationResourceEvaluationService


def test_seeding_and_evaluation(client):
    """Test that all 3 validation resources are seeded."""
    session_factory = get_session_factory()
    with session_factory() as session:
        # Run evaluation to register resources first
        service = ValidationResourceEvaluationService(session)
        service.register_resources()
        session.commit()

        stmt = select(ValidationResourceRegistryRow)
        resources = list(session.scalars(stmt))
        assert len(resources) == 6

        resource_names = {r.name for r in resources}
        expected_names = {
            "DeepEval",
            "Jaeger",
            "Zipkin",
            "Guardrails AI",
            "Pydantic AI",
            "Instructor",
        }
        assert expected_names.issubset(resource_names)


def test_api_endpoints_validation_evaluation(client):
    """Test the newly added endpoints for validation resource evaluation."""
    # 1. GET /api/validation-evaluation/resources
    r_res = client.get("/api/validation-evaluation/resources")
    assert r_res.status_code == 200
    resources = r_res.json()
    assert len(resources) == 6

    # 2. POST /api/validation-evaluation/evaluate
    os.environ["DPI_LS_TEST_MOCK_EVAL"] = "1"
    r_eval = client.post("/api/validation-evaluation/evaluate")
    assert r_eval.status_code == 200
    eval_results = r_eval.json()
    # 6 resources: DeepEval (6 metrics), Jaeger (8 metrics), Zipkin (7 metrics), Guardrails (4), Pydantic (3), Instructor (3) = 31 total results
    assert len(eval_results) == 31

    # 3. GET /api/validation-evaluation/results
    r_results = client.get("/api/validation-evaluation/results")
    assert r_results.status_code == 200
    latest_results = r_results.json()
    assert len(latest_results) == 31

    # Check that DeepEval answer_relevancy is detected
    deepeval_accuracy = [
        res for res in latest_results
        if res["resource_name"] == "DeepEval" and res["metric"] == "answer_relevancy"
    ]
    assert len(deepeval_accuracy) == 1
    assert deepeval_accuracy[0]["detected"] is False

    # 4. POST /api/validation-evaluation/verify-dashboard
    r_verify = client.post(
        "/api/validation-evaluation/verify-dashboard",
        json={"resource_name": "DeepEval", "metric": "answer_relevancy"}
    )
    assert r_verify.status_code == 200
    assert r_verify.json() == {"success": True}

    # Verify that the dashboard_verified flag is updated
    r_results2 = client.get("/api/validation-evaluation/results")
    latest_results2 = r_results2.json()
    deepeval_accuracy2 = [
        res for res in latest_results2
        if res["resource_name"] == "DeepEval" and res["metric"] == "answer_relevancy"
    ]
    assert deepeval_accuracy2[0]["dashboard_verified"] is True
