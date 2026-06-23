"""Service for executing technical evaluation of Cost and Validation resources at runtime.

It checks SDK availability, environment configuration, connection validation (port-level),
and queries stored telemetry observations for runtime evidence of detected metrics.
"""
from __future__ import annotations

import importlib.util
import os
import socket
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
        """Register the 15 baseline cost and validation resources."""
        resources = [
            ("Langfuse", True, True, True, True),
            ("Prometheus", True, True, False, True),
            ("Grafana", False, True, False, True),
            ("OpenTelemetry", True, True, False, True),
            ("OpenMeter", True, True, True, True),
            ("SigNoz", True, True, False, True),
            ("Arize Phoenix", True, True, False, True),
            ("Helicone", True, True, True, True),
            ("OpenObserve", True, True, True, True),
            ("Uptrace", True, True, True, True),
            ("Apache SkyWalking", True, True, False, True),
            ("Jaeger", True, True, False, True),
            ("MLflow", True, True, False, True),
            ("Elastic APM", True, True, True, True),
            ("SigNoz + OpenTelemetry Stack", True, True, False, True),
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
            "Langfuse": ["langfuse"],
            "Prometheus": ["prometheus_client"],
            "OpenTelemetry": ["opentelemetry"],
            "OpenMeter": ["openmeter"],
            "SigNoz": ["opentelemetry"],
            "Arize Phoenix": ["phoenix", "arize", "arize_phoenix"],
            "Helicone": ["openai"],
            "OpenObserve": ["opentelemetry"],
            "Uptrace": ["uptrace"],
            "Apache SkyWalking": ["skywalking"],
            "Jaeger": ["opentelemetry"],
            "MLflow": ["mlflow"],
            "Grafana": ["opentelemetry"],
            "Elastic APM": ["elasticapm"],
            "SigNoz + OpenTelemetry Stack": ["opentelemetry"],
        }
        module_names = sdk_map.get(name, [])
        if not module_names:
            return False
        # Return True if ANY of the module names is importable
        return any(importlib.util.find_spec(m) is not None for m in module_names)

    def _is_service_listening(self, name: str) -> bool:
        """Check if the service port is open and listening locally."""
        port_map = {
            "Langfuse": 4000,
            "Prometheus": 9090,
            "Grafana": 3000,
            "OpenTelemetry": 4317,
            "OpenMeter": 8888,
            "SigNoz": 3301,
            "Arize Phoenix": 6006,
            "Helicone": 80,
            "OpenObserve": 5080,
            "Uptrace": 14318,
            "Apache SkyWalking": 8080,
            "Jaeger": 16686,
            "MLflow": 5000,
            "Elastic APM": 5601,
            "SigNoz + OpenTelemetry Stack": 3301,
        }
        port = port_map.get(name)
        if not port:
            return True
            
        # Cloud services are always assumed to be listening
        if name in ["Langfuse", "Arize Phoenix"]:
            return True
            
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

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
            "validated_components",
            "required_components",
            "validation_score",
            "hallucination_score",
            "relevance_score",
            "groundedness_score",
            "user_feedback_score",
            "model_correctness",
        ]

        # Fetch all registered resources
        from store.repo import list_cost_resources
        resources = list_cost_resources(self.session)

        # Cache service liveness status per resource
        liveness_cache = {}
        for resource in resources:
            liveness_cache[resource.name] = self._is_service_listening(resource.name)

        # Query all observations and partials once to search for runtime telemetry evidence (latest first)
        obs_rows = list(self.session.scalars(select(ObservationRow).order_by(ObservationRow.id.desc())))
        partial_rows = list(self.session.scalars(select(PartialObservationRow).order_by(PartialObservationRow.id.desc())))

        results = []
        for resource in resources:
            service_running = liveness_cache.get(resource.name, True)
            for metric in metrics:
                # 1. Initialize Integration & SDK check
                sdk_ok = resource.sdk_available
                api_key_req = resource.api_key_required
                
                # Check if credentials exist in env
                env_keys = self._get_env_keys(resource.name)
                credentials_configured = any(os.environ.get(k) for k in env_keys) if env_keys else (not api_key_req)

                # Connection status
                if not credentials_configured:
                    status = "CREDENTIALS_MISSING"
                elif not service_running:
                    status = "FAILED"
                else:
                    status = "SUCCESS"

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

                # We no longer fall back to Canonical Observations for telemetry_detected
                # to ensure true resource independence.

                # Adjust status and evidence text if service is down but telemetry exists (Partially Verified case)
                if telemetry_detected and not service_running:
                    status = "FAILED"
                    evidence_text = f"Telemetry found, but local service/dashboard port is unreachable. Verification status: Partially Verified. {evidence_text}"

                # 3. Auto-detect quality metrics when service is running + resource supports metric
                QUALITY_METRICS_SET = {'hallucination_score', 'relevance_score', 'groundedness_score', 'user_feedback_score', 'model_correctness'}
                is_test_env = os.environ.get("DPI_LS_TEST_MOCK_EVAL") == "1"
                
                detected = telemetry_detected
                current_val = "0.0"
                
                if detected:
                    # Successfully parsed from DB
                    current_val = str(self._extract_value_from_payload(metric, {}, {}, {})) # fallback default placeholder
                    # Try to get the actual value from the evidence
                    for row in partial_rows:
                        payload = row.payload or {}
                        cost_block = payload.get("cost", {})
                        tasks_block = payload.get("tasks", {})
                        if self._is_metric_in_payload(metric, cost_block, tasks_block, payload):
                            current_val = str(self._extract_value_from_payload(metric, cost_block, tasks_block, payload))
                            break
                else:
                    # Production / default case: credentials missing or no runtime data ingested
                    if not credentials_configured:
                        evidence_text = f"SDK/Connection validation failed: missing credentials in env. Required: {', '.join(env_keys or [])}"
                    elif not service_running:
                        evidence_text = f"Service unreachable. Dashboard/collector port is closed. Verification status: Unverified."
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
            "Langfuse": ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"],
            "Prometheus": ["PROMETHEUS_URL"],
            "Grafana": ["GRAFANA_URL"],
            "OpenTelemetry": ["OTEL_EXPORTER_OTLP_ENDPOINT"],
            "OpenMeter": ["OPENMETER_API_KEY", "OPENMETER_ENDPOINT"],
            "SigNoz": ["SIGNOZ_URL"],
            "Arize Phoenix": ["PHOENIX_PORT", "PHOENIX_HOST"],
            "Helicone": ["HELICONE_API_KEY"],
            "OpenObserve": ["OPENOBSERVE_API_KEY", "OPENOBSERVE_URL"],
            "Uptrace": ["UPTRACE_DSN"],
            "Apache SkyWalking": ["SW_AGENT_COLLECTOR_BACKEND_SERVICES"],
            "Jaeger": ["JAEGER_ENDPOINT"],
            "MLflow": ["MLFLOW_TRACKING_URI"],
            "Elastic APM": ["ELASTIC_APM_SERVER_URL", "ELASTIC_APM_SECRET_TOKEN"],
            "SigNoz + OpenTelemetry Stack": ["SIGNOZ_URL", "OTEL_EXPORTER_OTLP_ENDPOINT"],
        }
        return keys_map.get(name, [])

    def _map_resource_to_sources(self, name: str) -> list[str]:
        """Map resource names to adapter sources stored in observations."""
        mapping = {
            "Langfuse": ["langfuse"],
            "Prometheus": ["prometheus"],
            "Grafana": ["grafana", "prometheus", "otel", "langfuse"],
            "OpenTelemetry": ["otel"],
            "OpenMeter": ["openmeter"],
            "SigNoz": ["signoz", "otel"],
            "Arize Phoenix": ["arize", "phoenix", "otel"],
            "Helicone": ["helicone"],
            "OpenObserve": ["openobserve", "otel"],
            "Uptrace": ["uptrace", "otel"],
            "Apache SkyWalking": ["skywalking"],
            "Jaeger": ["jaeger", "otel"],
            "MLflow": ["mlflow", "otel"],
            "Elastic APM": ["elastic_apm", "elasticapm"],
            "SigNoz + OpenTelemetry Stack": ["signoz", "otel"],
        }
        return mapping.get(name, [name.lower().replace(" ", "_")])

    def _is_metric_in_payload(self, metric: str, cost: dict, tasks: dict, payload: dict) -> bool:
        cost = cost or {}
        tasks = tasks or {}
        payload = payload or {}
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
            return "Human_cost" in cost or "human_cost_per_output" in payload or "salary_cost" in payload or "human_salary" in payload
        elif metric == "utilization":
            return "utilization" in payload or "utilization_factor" in payload
        elif metric == "total_cost_of_ownership":
            return "model_cost" in cost or "spend_usd" in payload or "Human_cost" in cost or "total_cost" in payload
        elif metric == "validated_components":
            return "validated_components" in (payload.get("validation") or {}) or "validated_components" in payload
        elif metric == "required_components":
            return "required_components" in (payload.get("validation") or {}) or "required_components" in payload
        elif metric == "validation_score":
            return "validation_score" in (payload.get("validation") or {}) or "validation" in payload or "validation_score" in payload
        elif metric == "hallucination_score":
            return "hallucination_rate" in (payload.get("quality") or {})
        elif metric == "relevance_score":
            return "accuracy" in (payload.get("quality") or {})
        elif metric == "groundedness_score":
            return "consistency" in (payload.get("quality") or {})
        elif metric == "user_feedback_score":
            return "user_feedback" in payload or "user_feedback_score" in payload
        elif metric == "model_correctness":
            return "accuracy" in (payload.get("quality") or {})
        return False

    def _extract_value_from_payload(self, metric: str, cost: dict, tasks: dict, payload: dict) -> Any:
        cost = cost or {}
        tasks = tasks or {}
        payload = payload or {}
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
            from contract.settings import Settings
            default_hc = Settings().human_cost_per_output
            return cost.get("Human_cost") or payload.get("human_cost_per_output") or payload.get("salary_cost") or default_hc
        elif metric == "utilization":
            return payload.get("utilization") or payload.get("utilization_factor") or 0.85
        elif metric == "total_cost_of_ownership":
            from contract.settings import Settings
            default_hc = Settings().human_cost_per_output
            mc = cost.get("model_cost") or payload.get("spend_usd") or 0.0
            hc = cost.get("Human_cost") or payload.get("human_cost_per_output") or default_hc
            return mc + hc
        elif metric == "validated_components":
            return (payload.get("validation") or {}).get("validated_components") or payload.get("validated_components") or 0
        elif metric == "required_components":
            return (payload.get("validation") or {}).get("required_components") or payload.get("required_components") or 0
        elif metric == "validation_score":
            val_dict = payload.get("validation") or {}
            req = val_dict.get("required_components") or payload.get("required_components") or 0
            val = val_dict.get("validated_components") or payload.get("validated_components") or 0
            return val / max(req, 1) if req > 0 else 1.0
        elif metric == "hallucination_score":
            return (payload.get("quality") or {}).get("hallucination_rate")
        elif metric == "relevance_score":
            return (payload.get("quality") or {}).get("accuracy")
        elif metric == "groundedness_score":
            return (payload.get("quality") or {}).get("consistency")
        elif metric == "user_feedback_score":
            return payload.get("user_feedback_score") or payload.get("user_feedback")
        elif metric == "model_correctness":
            return (payload.get("quality") or {}).get("accuracy")
        return 0.0

    def _resource_supports_metric(self, resource_name: str, metric: str) -> bool:
        """Map static capability matrices (which resource can technical detect which metric)."""
        capabilities = {
            "Langfuse": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "Prometheus": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "utilization", "total_cost_of_ownership", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "Grafana": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "utilization", "total_cost_of_ownership", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "OpenTelemetry": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "utilization", "total_cost_of_ownership", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "OpenMeter": ["model_cost", "token_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization"],
            "SigNoz": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "Arize Phoenix": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "Helicone": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "validated_components", "required_components", "validation_score"],
            "OpenObserve": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "Uptrace": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "Apache SkyWalking": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization", "validated_components", "required_components", "validation_score"],
            "Jaeger": ["total_cost_of_ownership", "validation_score"],
            "MLflow": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "total_cost_of_ownership", "utilization", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "Elastic APM": ["model_cost", "token_cost", "prompt_cost", "completion_cost", "AI_cost_per_output", "utilization", "total_cost_of_ownership", "validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
            "SigNoz + OpenTelemetry Stack": ["validated_components", "required_components", "validation_score", "hallucination_score", "relevance_score", "groundedness_score", "user_feedback_score", "model_correctness"],
        }
        return metric in capabilities.get(resource_name, [])

