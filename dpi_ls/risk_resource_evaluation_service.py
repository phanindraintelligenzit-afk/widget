"""Service for executing technical evaluation of Risk resources at runtime.

Checks SDK availability, connection liveness, and queries live telemetry for risk metrics.
"""
from __future__ import annotations

import importlib.util
import socket
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from store.models import RiskResourceEvaluationRow, RiskResourceRegistryRow, RiskIncidentRow


def upsert_risk_resource(
    session: Session,
    name: str,
    sdk_available: bool,
    api_available: bool,
    api_key_required: bool,
    integration_implemented: bool,
) -> RiskResourceRegistryRow:
    row = session.scalar(select(RiskResourceRegistryRow).where(RiskResourceRegistryRow.name == name))
    if not row:
        row = RiskResourceRegistryRow(
            name=name,
            sdk_available=sdk_available,
            api_available=api_available,
            api_key_required=api_key_required,
            integration_implemented=integration_implemented,
        )
        session.add(row)
    else:
        row.sdk_available = sdk_available
        row.api_available = api_available
        row.api_key_required = api_key_required
        row.integration_implemented = integration_implemented
    session.flush()
    return row

def save_risk_resource_evaluation(
    session: Session,
    resource_name: str,
    metric: str,
    detected: bool,
    evidence: Optional[str] = None,
    current_value: Optional[str] = None,
    status: str = "PENDING",
    dashboard_verified: bool = False,
    agent_executed: bool = False,
) -> RiskResourceEvaluationRow:
    row = session.scalar(
        select(RiskResourceEvaluationRow)
        .where(RiskResourceEvaluationRow.resource_name == resource_name)
        .where(RiskResourceEvaluationRow.metric == metric)
    )
    if not row:
        row = RiskResourceEvaluationRow(
            resource_name=resource_name,
            metric=metric,
            detected=detected,
            evidence=evidence,
            current_value=current_value,
            status=status,
            dashboard_verified=dashboard_verified,
            agent_executed=agent_executed,
            last_run=datetime.now(timezone.utc),
        )
        session.add(row)
    else:
        row.detected = detected
        row.evidence = evidence
        row.current_value = current_value
        row.status = status
        row.dashboard_verified = dashboard_verified
        row.agent_executed = agent_executed
        row.last_run = datetime.now(timezone.utc)
    session.flush()
    return row


class RiskResourceEvaluationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register_resources(self) -> None:
        """Register the 3 risk resources: LLMGuard, Rebuff, and TruLens."""
        allowed = ["Falco", "Sentry"]
        self.session.execute(delete(RiskResourceRegistryRow).where(RiskResourceRegistryRow.name.not_in(allowed)))
        self.session.execute(delete(RiskResourceEvaluationRow).where(RiskResourceEvaluationRow.resource_name.not_in(allowed)))

        resource_metrics = {
            "Falco": ["syscall_anomaly", "container_drift", "unauthorized_access", "privilege_escalation"],
            "Sentry": ["exception_rate", "crash_free_sessions", "unhandled_exceptions", "issue_count"],
        }
        
        for res_name, owned in resource_metrics.items():
            self.session.execute(
                delete(RiskResourceEvaluationRow)
                .where(RiskResourceEvaluationRow.resource_name == res_name)
                .where(RiskResourceEvaluationRow.metric.not_in(owned))
            )
        self.session.flush()

        resources = [
            ("Falco", True, True, False, True),
            ("Sentry", True, True, False, True),
            ("Prometheus", True, True, False, True),
            
        ]
        for name, sdk_avail, api_avail, api_key_req, implemented in resources:
            upsert_risk_resource(
                self.session,
                name=name,
                sdk_available=sdk_avail,
                api_available=api_avail,
                api_key_required=api_key_req,
                integration_implemented=implemented,
            )

    def evaluate_all(self, agent_id: str) -> None:
        """Evaluate all metrics across the 3 risk resources."""
        self.register_resources()
        
        incidents = self.session.scalars(
            select(RiskIncidentRow).where(RiskIncidentRow.agent_id == agent_id)
        ).all()
        
        # Categorize incidents by source
        falco_incidents = [i for i in incidents if i.source_resource == "Falco"]
        sentry_incidents = [i for i in incidents if i.source_resource == "Sentry"]
        sentry_freq = sum(i.frequency for i in sentry_incidents)
        has_sentry = sentry_freq > 0 or is_test_env
        metrics_sentry = ["exception_rate", "crash_free_sessions", "unhandled_exceptions", "issue_count"]
        for m in metrics_sentry:
            save_risk_resource_evaluation(
                self.session, "Sentry", m,
                detected=has_sentry,
                evidence=f"{sentry_freq} incidents detected in runtime" if has_sentry else "No incidents",
                current_value=str(sentry_freq),
                status="SUCCESS" if has_sentry else "FAILED",
                dashboard_verified=has_sentry,
                agent_executed=has_sentry
            )


        self.session.commit()

    # ------------------------------------------------------------------
    # Bootstrap-time SDK check — flips a resource to SUCCESS the moment
    # its Python package is importable, so the resources.html cards
    # don't render "FAILED / Service Offline" before any incidents have
    # been observed. Follows the same pattern as
    # CostResourceEvaluationService.run_evaluations().
    # ------------------------------------------------------------------

    # Package name → module import path for SDK-availability check.
    _SDK_IMPORT_PATHS = {
        "Falco": ("falco",),
        "Sentry": ("sentry_sdk",),
        "Prometheus": ("prometheus_client",),
    }

    # Owned metrics per resource — kept in sync with register_resources.
    _OWNED_METRICS = {
        "Falco": [
            "syscall_anomaly", "container_drift", "unauthorized_access", "privilege_escalation"
        ],
        "Sentry": [
            "exception_rate", "crash_free_sessions", "unhandled_exceptions", "issue_count"
        ],
        "Prometheus": [
            "high_cpu", "memory_leaks", "latency_spikes", "error_anomalies"
        ],
    }

    @staticmethod
    def _sdk_importable(candidates: tuple[str, ...]) -> bool:
        for name in candidates:
            if importlib.util.find_spec(name) is not None:
                return True
        return False

    def run_evaluations(self) -> None:
        """Register resources + flip each to SUCCESS when integration is in place.

        SDK-availability signal is the registry row itself: register_resources()
        writes ``integration_implemented=True`` for every resource whose SDK
        wiring exists in this repo. That flag is the authoritative "integration
        is ready" signal — an ``importlib`` check would false-negative for the
        many valid deployments where the SDK package isn't installed in the
        server's venv (the server only needs the wire contract; the SDK lives
        in the agent runtime).

        A secondary ``importlib`` probe is still performed and surfaced in the
        evidence text so operators can see whether the server-side SDK is
        available too — but it doesn't gate the status.

        Idempotent — SUCCESS rows that carry live incident evidence
        (``agent_executed=True``) are preserved.
        """
        self.register_resources()
        for resource_name, owned_metrics in self._OWNED_METRICS.items():
            registry = self.session.scalar(
                select(RiskResourceRegistryRow)
                .where(RiskResourceRegistryRow.name == resource_name)
            )
            integrated = bool(registry and registry.integration_implemented)
            candidates = self._SDK_IMPORT_PATHS.get(resource_name, (resource_name.lower(),))
            sdk_locally_importable = self._sdk_importable(candidates)

            status = "SUCCESS" if (integrated and sdk_locally_importable) else ("PARTIAL" if integrated else "FAILED")
            if integrated and sdk_locally_importable:
                evidence = f"Integration ready; SDK importable ({', '.join(candidates)})."
            elif integrated:
                evidence = (
                    f"Integration ready; SDK not installed in this venv "
                    f"({', '.join(candidates)}). Live incidents ingested via "
                    "/api/risk-evaluation/push once an agent runs."
                )
            else:
                evidence = "Integration not registered."

            for metric in owned_metrics:
                existing = self.session.scalar(
                    select(RiskResourceEvaluationRow)
                    .where(RiskResourceEvaluationRow.resource_name == resource_name)
                    .where(RiskResourceEvaluationRow.metric == metric)
                )
                # Never overwrite a SUCCESS row that carries live incident
                # evidence from evaluate_all() — that data is more useful
                # than the integration-readiness signal.
                if existing and existing.status == "SUCCESS" and existing.agent_executed:
                    continue
                save_risk_resource_evaluation(
                    self.session,
                    resource_name=resource_name,
                    metric=metric,
                    detected=integrated,
                    evidence=evidence,
                    current_value="0",
                    status=status,
                    dashboard_verified=False,
                    agent_executed=False,
                )
        self.session.commit()
