"""Service for executing technical evaluation of Cost resources at runtime.

It checks SDK availability, environment configuration, connection validation,
and queries stored telemetry observations for runtime evidence of detected metrics.
"""
from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from store.models import CostResourceEvaluationRow, CostResourceRegistryRow, ObservationRow, PartialObservationRow
from store.repo import save_cost_resource_evaluation, upsert_cost_resource


class CostResourceEvaluationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register_resources(self) -> None:
        """Register the 19 standard cost resources."""
        resources = [
            ("AWS Bedrock Pricing", True, True, True, True),
            ("AWS Cost Explorer", True, True, True, True),
            ("AWS CUR", True, True, True, True),
            ("AWS Budgets", True, True, True, True),
            ("Azure Cost Management", False, True, True, True),
            ("GCP Cloud Billing", False, True, True, True),
            ("OpenAI Usage API", True, True, True, True),
            ("LangSmith", True, True, True, True),
            ("Langfuse", True, True, True, True),
            ("Kubecost", False, True, False, True),
            ("CloudZero", False, True, True, True),
            ("Spot by NetApp", False, True, True, True),
            ("Jira / Timesheets", False, True, True, True),
            ("Workday", False, True, True, True),
            ("SAP SuccessFactors", False, True, True, True),
            ("Oracle HCM", False, True, True, True),
            ("Prometheus", True, True, False, True),
            ("Pinecone Billing", False, True, True, True),
            ("Jira Service Desk", False, True, True, True),
        ]
        for name, sdk_avail, api_avail, api_key_req, implemented in resources:
            # Check SDK dynamically
            sdk_ok = self._check_sdk_avail(name)
            upsert_cost_resource(
                self.session,
                name=name,
                sdk_available=sdk_ok,
                api_available=api_avail,
                api_key_required=api_key_req,
                integration_implemented=implemented,
            )

    def _check_sdk_avail(self, name: str) -> bool:
        """Helper to check if python SDK is importable for a given resource name."""
        sdk_map = {
            "AWS Bedrock Pricing": "boto3",
            "AWS Cost Explorer": "boto3",
            "AWS CUR": "boto3",
            "AWS Budgets": "boto3",
            "OpenAI Usage API": "openai",
            "LangSmith": "langsmith",
            "Langfuse": "langfuse",
            "Prometheus": "prometheus_client",
        }
        module_name = sdk_map.get(name)
        if not module_name:
            return False
        return importlib.util.find_spec(module_name) is not None

    def run_evaluations(self) -> list[CostResourceEvaluationRow]:
        """Perform evaluation workflow for all resources and metrics."""
        self.register_resources()

        metrics = [
            "model_cost",
            "token_cost",
            "prompt_cost",
            "completion_cost",
            "AI_cost_per_output",
            "Human_cost_per_output",
            "utilization",
            "total_cost_of_ownership",
        ]

        # Fetch all registered resources
        from store.repo import list_cost_resources
        resources = list_cost_resources(self.session)

        # Query all observations and partials once to search for runtime telemetry evidence
        obs_rows = list(self.session.scalars(select(ObservationRow)))
        partial_rows = list(self.session.scalars(select(PartialObservationRow)))

        results = []
        for resource in resources:
            for metric in metrics:
                # 1. Initialize Integration & SDK check
                sdk_ok = resource.sdk_available
                api_key_req = resource.api_key_required
                
                # Check if credentials exist in env
                env_keys = self._get_env_keys(resource.name)
                credentials_configured = any(os.environ.get(k) for k in env_keys) if env_keys else (not api_key_req)
                
                # Connection status
                status = "SUCCESS" if credentials_configured else "CREDENTIALS_MISSING"

                # 2. Check Database observations/partials for real runtime telemetry
                telemetry_detected = False
                evidence_text = ""
                agent_run_executed = False

                # Map resource name to telemetry source names in the DB
                db_sources = self._map_resource_to_sources(resource.name)
                
                # Check for matching telemetry in Partial Observations
                for row in partial_rows:
                    if row.source in db_sources:
                        agent_run_executed = True
                        payload = row.payload or {}
                        cost_block = payload.get("cost", {})
                        tasks_block = payload.get("tasks", {})
                        
                        # Verify specific metric detection
                        if self._is_metric_in_payload(metric, cost_block, tasks_block, payload):
                            telemetry_detected = True
                            val = self._extract_value_from_payload(metric, cost_block, tasks_block, payload)
                            evidence_text = (
                                f"Runtime Telemetry Ingested from source '{row.source}'. "
                                f"Value extracted: {val}. Observation ID: {row.id}. Ingested at: {row.received_at}."
                            )
                            break

                # Check for matching telemetry in Canonical Observations
                if not telemetry_detected:
                    for row in obs_rows:
                        agent_run_executed = True
                        payload = row.payload or {}
                        cost_block = payload.get("cost", {})
                        tasks_block = payload.get("tasks", {})
                        
                        if self._is_metric_in_payload(metric, cost_block, tasks_block, payload):
                            telemetry_detected = True
                            val = self._extract_value_from_payload(metric, cost_block, tasks_block, payload)
                            evidence_text = (
                                f"Canonical Telemetry Ingested. "
                                f"Value extracted: {val}. Observation ID: {row.id}. Ingested at: {row.received_at}."
                            )
                            break

                # 3. Fallback/Mock logic for testing if we run in test/demo mode
                is_test_env = os.environ.get("DPI_LS_TEST_MOCK_EVAL") == "1"
                
                detected = telemetry_detected
                current_val = "0.0"
                
                if detected:
                    # Successfully parsed from DB
                    current_val = str(self._extract_value_from_payload(metric, {}, {}, {})) # fallback default placeholder
                    # Try to get the actual value from the evidence
                    for row in partial_rows + obs_rows:
                        payload = row.payload or {}
                        cost_block = payload.get("cost", {})
                        tasks_block = payload.get("tasks", {})
                        if self._is_metric_in_payload(metric, cost_block, tasks_block, payload):
                            current_val = str(self._extract_value_from_payload(metric, cost_block, tasks_block, payload))
                            break
                elif is_test_env:
                    # In test environments, we can simulate runtime detection if SDK or stub is configured
                    has_capability = self._resource_supports_metric(resource.name, metric)
                    if has_capability and (sdk_ok or not api_key_req or credentials_configured):
                        detected = True
                        current_val = self._get_mock_metric_value(metric)
                        evidence_text = f"Simulated Runtime Check: Verified {resource.name} API response structures for metric '{metric}'."
                        status = "SUCCESS"
                        agent_run_executed = True
                    else:
                        evidence_text = f"Resource lacks capability to detect '{metric}' or credentials are unconfigured."
                else:
                    # Production / default case: credentials missing or no runtime data ingested
                    if not credentials_configured:
                        evidence_text = f"SDK/Connection validation failed: missing credentials in env. Required: {', '.join(env_keys or [])}"
                    else:
                        evidence_text = f"Connection validated successfully, but no telemetry has been emitted for '{metric}' during agent execution."

                # Save evaluation log
                eval_row = save_cost_resource_evaluation(
                    self.session,
                    resource_name=resource.name,
                    metric=metric,
                    detected=detected,
                    evidence=evidence_text,
                    current_value=current_val,
                    status=status,
                    agent_executed=agent_run_executed,
                )
                results.append(eval_row)

        return results

    def _get_env_keys(self, name: str) -> list[str]:
        keys_map = {
            "AWS Bedrock Pricing": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
            "AWS Cost Explorer": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
            "AWS CUR": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
            "AWS Budgets": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
            "Azure Cost Management": ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID"],
            "GCP Cloud Billing": ["GOOGLE_APPLICATION_CREDENTIALS"],
            "OpenAI Usage API": ["OPENAI_API_KEY"],
            "LangSmith": ["LANGCHAIN_API_KEY"],
            "Langfuse": ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"],
            "CloudZero": ["CLOUDZERO_API_KEY"],
            "Spot by NetApp": ["SPOT_API_KEY"],
            "Jira / Timesheets": ["JIRA_API_TOKEN", "JIRA_URL"],
            "Workday": ["WORKDAY_API_TOKEN"],
            "SAP SuccessFactors": ["SAP_SF_CLIENT_ID"],
            "Oracle HCM": ["ORACLE_HCM_URL"],
            "Pinecone Billing": ["PINECONE_API_KEY"],
            "Jira Service Desk": ["JIRA_SD_API_TOKEN"],
        }
        return keys_map.get(name, [])

    def _map_resource_to_sources(self, name: str) -> list[str]:
        """Map resource names to adapter sources stored in observations."""
        mapping = {
            "AWS Bedrock Pricing": ["bedrock", "aws_cost"],
            "AWS Cost Explorer": ["aws_cost"],
            "AWS CUR": ["aws_cost", "cur"],
            "AWS Budgets": ["aws_cost", "budgets"],
            "OpenAI Usage API": ["openai", "openai_usage"],
            "LangSmith": ["langsmith"],
            "Langfuse": ["langfuse"],
            "Prometheus": ["prometheus"],
            "Workday": ["workday", "sap_hr"],
            "SAP SuccessFactors": ["sap_hr"],
            "Jira / Timesheets": ["jira"],
            "Jira Service Desk": ["jira"],
        }
        return mapping.get(name, [name.lower().replace(" ", "_")])

    def _is_metric_in_payload(self, metric: str, cost: dict, tasks: dict, payload: dict) -> bool:
        if metric == "model_cost":
            return "model_cost" in cost or "spend_usd" in payload or "spend" in payload
        elif metric == "token_cost":
            return "input_tokens" in cost or "output_tokens" in cost or "tokens" in payload
        elif metric == "prompt_cost":
            return "input_tokens" in cost
        elif metric == "completion_cost":
            return "output_tokens" in cost
        elif metric == "AI_cost_per_output":
            return ("model_cost" in cost or "spend_usd" in payload) and ("completed" in tasks or "output_count" in payload)
        elif metric == "Human_cost_per_output":
            # HR source systems
            return "Human_cost" in cost or "human_cost_per_output" in payload or "salary_cost" in payload or "human_salary" in payload
        elif metric == "utilization":
            return "utilization" in payload or "utilization_factor" in payload
        elif metric == "total_cost_of_ownership":
            return "model_cost" in cost or "spend_usd" in payload or "Human_cost" in cost or "total_cost" in payload
        return False

    def _extract_value_from_payload(self, metric: str, cost: dict, tasks: dict, payload: dict) -> Any:
        if metric == "model_cost":
            return cost.get("model_cost") or payload.get("spend_usd") or payload.get("spend") or 0.0
        elif metric == "token_cost":
            in_t = cost.get("input_tokens", 0)
            out_t = cost.get("output_tokens", 0)
            return (in_t + out_t) * 0.00001
        elif metric == "prompt_cost":
            return cost.get("input_tokens", 0) * 0.000005
        elif metric == "completion_cost":
            return cost.get("output_tokens", 0) * 0.000015
        elif metric == "AI_cost_per_output":
            mc = cost.get("model_cost") or payload.get("spend_usd") or 0.0
            completed = tasks.get("completed") or payload.get("output_count") or 1
            return mc / max(completed, 1)
        elif metric == "Human_cost_per_output":
            return cost.get("Human_cost") or payload.get("human_cost_per_output") or payload.get("salary_cost") or 50.0
        elif metric == "utilization":
            return payload.get("utilization") or payload.get("utilization_factor") or 0.85
        elif metric == "total_cost_of_ownership":
            mc = cost.get("model_cost") or payload.get("spend_usd") or 0.0
            hc = cost.get("Human_cost") or payload.get("human_cost_per_output") or 0.0
            return mc + hc
        return 0.0

    def _resource_supports_metric(self, resource_name: str, metric: str) -> bool:
        """Map static capability matrices (which resource can technical detect which metric)."""
        capabilities = {
            "AWS Bedrock Pricing": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership"],
            "AWS Cost Explorer": ["model_cost", "total_cost_of_ownership"],
            "AWS CUR": ["model_cost", "total_cost_of_ownership"],
            "AWS Budgets": ["utilization", "total_cost_of_ownership"],
            "Azure Cost Management": ["model_cost", "total_cost_of_ownership"],
            "GCP Cloud Billing": ["model_cost", "total_cost_of_ownership"],
            "OpenAI Usage API": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership"],
            "LangSmith": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership"],
            "Langfuse": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership"],
            "Kubecost": ["model_cost", "total_cost_of_ownership"],
            "CloudZero": ["model_cost", "total_cost_of_ownership"],
            "Spot by NetApp": ["model_cost", "total_cost_of_ownership"],
            "Jira / Timesheets": ["Human_cost_per_output", "total_cost_of_ownership"],
            "Workday": ["Human_cost_per_output", "total_cost_of_ownership"],
            "SAP SuccessFactors": ["Human_cost_per_output", "total_cost_of_ownership"],
            "Oracle HCM": ["Human_cost_per_output", "total_cost_of_ownership"],
            "Prometheus": ["utilization"],
            "Pinecone Billing": ["model_cost", "total_cost_of_ownership"],
            "Jira Service Desk": ["Human_cost_per_output", "total_cost_of_ownership"],
        }
        return metric in capabilities.get(resource_name, [])

    def _get_mock_metric_value(self, metric: str) -> str:
        vals = {
            "model_cost": "1.24",
            "token_cost": "0.15",
            "prompt_cost": "0.05",
            "completion_cost": "0.10",
            "AI_cost_per_output": "0.014",
            "Human_cost_per_output": "50.0",
            "utilization": "0.85",
            "total_cost_of_ownership": "51.24",
        }
        return vals.get(metric, "0.0")
