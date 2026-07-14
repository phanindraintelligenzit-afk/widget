from __future__ import annotations
import os, time
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from store.models import ExecutionResourceEvaluationRow, ExecutionResourceRegistryRow, ScoreRow
from store.repo import save_execution_resource_evaluation, upsert_execution_resource, list_latest_execution_resource_evaluations

class ExecutionResourceEvaluationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register_resources(self) -> None:
        allowed = ["Langfuse", "Phoenix", "Traceloop"]
        self.session.execute(delete(ExecutionResourceRegistryRow).where(ExecutionResourceRegistryRow.name.not_in(allowed)))
        self.session.execute(delete(ExecutionResourceEvaluationRow).where(ExecutionResourceEvaluationRow.resource_name.not_in(allowed)))

        resource_metrics = {
            "Langfuse": ["trace_captured", "execution_success"],
            "Phoenix": ["iterations_used", "execution_status"],
            "Traceloop": ["workflow_execution"]
        }
        for res_name, owned in resource_metrics.items():
            self.session.execute(
                delete(ExecutionResourceEvaluationRow)
                .where(ExecutionResourceEvaluationRow.resource_name == res_name)
                .where(ExecutionResourceEvaluationRow.metric.not_in(owned))
            )
        self.session.flush()

        resources = [
            ("Langfuse", True, True, False, True),
            ("Phoenix", True, True, False, True),
            ("Traceloop", True, True, False, True),
        ]
        for name, sdk_avail, api_avail, api_key_req, implemented in resources:
            upsert_execution_resource(
                self.session,
                name=name,
                sdk_available=sdk_avail,
                api_available=api_avail,
                api_key_required=api_key_req,
                integration_implemented=implemented,
            )

    def run_evaluations(self) -> list[ExecutionResourceEvaluationRow]:
        self.register_resources()
        
        resource_metrics = {
            "Langfuse": ["trace_captured", "execution_success"],
            "Phoenix": ["iterations_used", "execution_status"],
            "Traceloop": ["workflow_execution"]
        }
        
        # Check existing evaluations
        existing = list_latest_execution_resource_evaluations(self.session)
        existing_map = {f"{r.resource_name}:{r.metric}": r for r in existing}
        
        rows = []
        for res_name, metrics in resource_metrics.items():
            for metric in metrics:
                key = f"{res_name}:{metric}"
                if key in existing_map:
                    rows.append(existing_map[key])
                else:
                    # Create default "Unavailable" row
                    row = save_execution_resource_evaluation(
                        self.session,
                        resource_name=res_name,
                        metric=metric,
                        detected=False,
                        evidence="No runtime telemetry captured yet. Awaiting execution.",
                        current_value="Unavailable",
                        status="FAILED"
                    )
                    rows.append(row)
        
        self.session.flush()
        return rows
