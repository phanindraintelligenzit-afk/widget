import os
from sqlalchemy import select
from store.db import get_session_factory
from store.models import CostResourceRegistryRow, CostResourceEvaluationRow
from dpi_ls.cost_resource_evaluation_service import CostResourceEvaluationService


def test_seeding_and_evaluation(client):
    """Test that all 19 resources are seeded and initial evaluations are stored."""
    # Obtain a session and verify
    session_factory = get_session_factory()
    with session_factory() as session:
        # Check resources in DB (should have been seeded on startup by bootstrap)
        stmt = select(CostResourceRegistryRow)
        resources = list(session.scalars(stmt))
        assert len(resources) == 19

        resource_names = {r.name for r in resources}
        expected_names = {
            "AWS Bedrock Pricing",
            "AWS Cost Explorer",
            "AWS CUR",
            "AWS Budgets",
            "Azure Cost Management",
            "GCP Cloud Billing",
            "OpenAI Usage API",
            "LangSmith",
            "Langfuse",
            "Kubecost",
            "CloudZero",
            "Spot by NetApp",
            "Jira / Timesheets",
            "Workday",
            "SAP SuccessFactors",
            "Oracle HCM",
            "Prometheus",
            "Pinecone Billing",
            "Jira Service Desk",
        }
        assert expected_names.issubset(resource_names)


def test_api_endpoints_cost_evaluation(client):
    """Test the newly added endpoints for cost resource evaluation."""
    # 1. GET /api/cost-evaluation/resources
    r_res = client.get("/api/cost-evaluation/resources")
    assert r_res.status_code == 200
    resources = r_res.json()
    assert len(resources) == 19

    # 2. POST /api/cost-evaluation/evaluate
    os.environ["DPI_LS_TEST_MOCK_EVAL"] = "1"
    r_eval = client.post("/api/cost-evaluation/evaluate")
    assert r_eval.status_code == 200
    eval_results = r_eval.json()
    # 19 resources * 8 metrics = 152 evaluation results
    assert len(eval_results) == 152

    # 3. GET /api/cost-evaluation/results
    r_results = client.get("/api/cost-evaluation/results")
    assert r_results.status_code == 200
    latest_results = r_results.json()
    assert len(latest_results) == 152

    # Check that OpenAI Usage API got token_cost detected as True in mock test environment
    openai_token_cost = [
        res for res in latest_results
        if res["resource_name"] == "OpenAI Usage API" and res["metric"] == "token_cost"
    ]
    assert len(openai_token_cost) == 1
    assert openai_token_cost[0]["detected"] is True

    # 4. POST /api/cost-evaluation/verify-dashboard
    r_verify = client.post(
        "/api/cost-evaluation/verify-dashboard",
        json={"resource_name": "OpenAI Usage API", "metric": "token_cost"}
    )
    assert r_verify.status_code == 200
    assert r_verify.json() == {"success": True}

    # Verify that the dashboard_verified flag is updated
    r_results2 = client.get("/api/cost-evaluation/results")
    latest_results2 = r_results2.json()
    openai_token_cost2 = [
        res for res in latest_results2
        if res["resource_name"] == "OpenAI Usage API" and res["metric"] == "token_cost"
    ]
    assert openai_token_cost2[0]["dashboard_verified"] is True
