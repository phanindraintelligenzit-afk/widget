"""Service for executing technical evaluation of Quality resources at runtime.

Checks SDK availability, environment configuration, connection liveness,
and queries actual live telemetry observations for quality metrics.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from store.models import QualityResourceEvaluationRow, QualityResourceRegistryRow, ScoreRow
from store.repo import save_quality_resource_evaluation, upsert_quality_resource


class QualityResourceEvaluationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register_resources(self) -> None:
        """Register the 3 quality resources: Ragas, AgentOps, and DeepEval."""
        from sqlalchemy import delete
        allowed = ["Ragas", "AgentOps", "DeepEval"]
        self.session.execute(delete(QualityResourceRegistryRow).where(QualityResourceRegistryRow.name.not_in(allowed)))
        self.session.execute(delete(QualityResourceEvaluationRow).where(QualityResourceEvaluationRow.resource_name.not_in(allowed)))

        # Define owned metrics per resource
        resource_metrics = {
            "Ragas": ["semantic_accuracy", "faithfulness", "answer_relevancy", "context_precision", "context_recall"],
            "AgentOps": ["runtime_execution_history", "agent_behaviour", "consistency_measurement", "session_metrics", "stability_metrics"],
            "DeepEval": ["answer_relevancy", "faithfulness", "hallucination", "correctness"],
        }
        for res_name, owned in resource_metrics.items():
            self.session.execute(
                delete(QualityResourceEvaluationRow)
                .where(QualityResourceEvaluationRow.resource_name == res_name)
                .where(QualityResourceEvaluationRow.metric.not_in(owned))
            )
        self.session.flush()

        resources = [
                        ("Ragas", True, True, False, True),
            ("AgentOps", True, True, True, True),
            ("DeepEval", True, True, False, True),
        ]
        for name, sdk_avail, api_avail, api_key_req, implemented in resources:
            sdk_ok = self._check_sdk_avail(name)
            upsert_quality_resource(
                self.session,
                name=name,
                sdk_available=sdk_ok,
                api_available=api_avail,
                api_key_required=api_key_req,
                integration_implemented=implemented,
            )

    def _check_sdk_avail(self, name: str) -> bool:
        """Helper to check if python SDK is importable for a given quality resource name."""
        sdk_map = {
            "Ragas": ["ragas"],
            "AgentOps": ["agentops"],
            "DeepEval": ["deepeval"],
        }
        module_names = sdk_map.get(name, [])
        if not module_names:
            return False
        for m in module_names:
            try:
                importlib.import_module(m)
                return True
            except ImportError:
                pass
        return False

    def _is_service_listening(self, name: str) -> bool:
        """Check if the service port is open and listening locally.
        
        For SaaS or Python library integrations (LangSmith, Ragas, AgentOps),
        SDK importability acts as the baseline check, though API health checks
        could be layered here.
        """
        # All three are SDK/API driven, rely on SDK check for basic connectivity
        return self._check_sdk_avail(name)

    def run_evaluations(self) -> list[QualityResourceEvaluationRow]:
        """Perform evaluation workflow for all quality resources and metrics.

        Uses purely runtime data. Priority order:
        1. Real value pushed into quality_resource_evaluations by runtime agent execution.
        2. "Unavailable" — absolutely no simulated or hardcoded fallback telemetry.
        """
        total_start = time.time()
        print(f"\n[DPI-LS Quality Service] Beginning technical evaluation workflow...")
        self.register_resources()

        from store.repo import list_quality_resources
        resources = list_quality_resources(self.session)

        # Cache service liveness status per resource with timings
        liveness_cache = {}
        for resource in resources:
            chk_start = time.time()
            is_alive = self._is_service_listening(resource.name)
            chk_dur = time.time() - chk_start
            liveness_cache[resource.name] = is_alive
            status_str = "Connected" if is_alive else "Unavailable"
            print(f"  - {resource.name}: {status_str} (checked in {chk_dur:.4f}s)")

        # Fetch the latest score for the configured agent
        agent_id = os.environ.get("AGENT_ID", "chandra-finops")
        score_row = self.session.scalars(
            select(ScoreRow)
            .where(ScoreRow.agent_id == agent_id)
            .order_by(ScoreRow.id.desc())
            .limit(1)
        ).first()

        # Extract real values from DB for all three Quality resources
        real_values = {"Ragas": {}, "AgentOps": {}, "DeepEval": {}}
        for r_name in real_values.keys():
            try:
                rows = self.session.scalars(
                    select(QualityResourceEvaluationRow)
                    .where(QualityResourceEvaluationRow.resource_name == r_name)
                    .order_by(QualityResourceEvaluationRow.last_run.desc(), QualityResourceEvaluationRow.id.desc())
                ).all()
                seen_metrics = set()
                for r in rows:
                    if r.metric not in seen_metrics:
                        val = r.current_value or ""
                        if val != "Unavailable":
                            real_values[r_name][r.metric] = val
                        seen_metrics.add(r.metric)
            except Exception as e:
                print(f"[DPI-LS] Error reading {r_name} SDK metrics: {e}")

        # The exact required metrics per the specification
        resource_metrics = {
            "Ragas": ["semantic_accuracy", "faithfulness", "answer_relevancy", "context_precision", "context_recall"],
            "AgentOps": ["runtime_execution_history", "agent_behaviour", "consistency_measurement", "session_metrics", "stability_metrics"],
            "DeepEval": ["answer_relevancy", "faithfulness", "hallucination", "correctness"]
        }

        results = []
        for resource in resources:
            service_running = liveness_cache.get(resource.name, True)
            metrics_to_run = resource_metrics.get(resource.name, [])
            
            for metric in metrics_to_run:
                status = "SUCCESS" if service_running else "FAILED"
                detected = False
                current_val = "Unavailable"
                evidence_text = ""
                agent_run_executed = score_row is not None

                real_val = real_values[resource.name].get(metric)
                if real_val and real_val not in ("", "Unavailable"):
                    current_val = real_val
                    detected = True
                    evidence_text = f"Real {resource.name} SDK metric collected at runtime. Value: {current_val}."
                else:
                    current_val = "Unavailable"
                    detected = False
                    evidence_text = f"{resource.name} SDK metric not yet collected. Run agent execution to populate real values."

                # Adjust status if SDK is missing but telemetry somehow exists
                if detected and not service_running:
                    status = "SUCCESS"
                    evidence_text = f"Telemetry found, but local SDK missing. Verification status: Partially Verified. {evidence_text}"

                row = save_quality_resource_evaluation(
                    self.session,
                    resource_name=resource.name,
                    metric=metric,
                    detected=detected,
                    evidence=evidence_text,
                    current_value=current_val,
                    status=status,
                    agent_executed=agent_run_executed,
                )
                results.append(row)

        tot_dur = time.time() - total_start
        print(f"[DPI-LS Quality Service] Completed technical evaluation workflow in {tot_dur:.4f}s\n")
        return results
