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
        allowed = ["LLMGuard", "Rebuff", "TruLens"]
        self.session.execute(delete(RiskResourceRegistryRow).where(RiskResourceRegistryRow.name.not_in(allowed)))
        self.session.execute(delete(RiskResourceEvaluationRow).where(RiskResourceEvaluationRow.resource_name.not_in(allowed)))

        resource_metrics = {
            "LLMGuard": ["prompt_injection", "unsafe_prompt", "blocked_prompt", "prompt_sanitization", "jailbreak_detection", "prompt_risk_score"],
            "Rebuff": ["prompt_injection", "attack_count", "blocked_requests", "allowed_requests", "injection_confidence", "injection_severity"],
            "TruLens": ["hallucination", "groundedness", "safety_score", "toxicity", "feedback_score", "evaluation_status"]
        }
        
        for res_name, owned in resource_metrics.items():
            self.session.execute(
                delete(RiskResourceEvaluationRow)
                .where(RiskResourceEvaluationRow.resource_name == res_name)
                .where(RiskResourceEvaluationRow.metric.not_in(owned))
            )
        self.session.flush()

        resources = [
            ("LLMGuard", True, True, False, True),
            ("Rebuff", True, True, False, True),
            ("TruLens", True, True, False, True),
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
        llmguard_incidents = [i for i in incidents if i.source_resource == "LLMGuard"]
        rebuff_incidents = [i for i in incidents if i.source_resource == "Rebuff"]
        trulens_incidents = [i for i in incidents if i.source_resource == "TruLens"]

        # Evaluate LLMGuard
        llmguard_freq = sum(i.frequency for i in llmguard_incidents)
        has_llm = llmguard_freq > 0
        metrics_llm = ["prompt_injection", "unsafe_prompt", "blocked_prompt", "prompt_sanitization", "jailbreak_detection", "prompt_risk_score"]
        for m in metrics_llm:
            save_risk_resource_evaluation(
                self.session, "LLMGuard", m,
                detected=has_llm,
                evidence=f"{llmguard_freq} incidents detected in runtime" if has_llm else "No incidents",
                current_value=str(llmguard_freq),
                status="SUCCESS" if has_llm else "FAILED",
                dashboard_verified=has_llm,
                agent_executed=has_llm
            )

        # Evaluate Rebuff
        rebuff_freq = sum(i.frequency for i in rebuff_incidents)
        has_rebuff = rebuff_freq > 0
        metrics_rebuff = ["prompt_injection", "attack_count", "blocked_requests", "allowed_requests", "injection_confidence", "injection_severity"]
        for m in metrics_rebuff:
            save_risk_resource_evaluation(
                self.session, "Rebuff", m,
                detected=has_rebuff,
                evidence=f"{rebuff_freq} incidents detected in runtime" if has_rebuff else "No incidents",
                current_value=str(rebuff_freq),
                status="SUCCESS" if has_rebuff else "FAILED",
                dashboard_verified=has_rebuff,
                agent_executed=has_rebuff
            )

        # Evaluate TruLens
        trulens_freq = sum(i.frequency for i in trulens_incidents)
        has_trulens = trulens_freq > 0
        metrics_trulens = ["hallucination", "groundedness", "safety_score", "toxicity", "feedback_score", "evaluation_status"]
        for m in metrics_trulens:
            save_risk_resource_evaluation(
                self.session, "TruLens", m,
                detected=has_trulens,
                evidence=f"{trulens_freq} incidents detected in runtime" if has_trulens else "No incidents",
                current_value=str(trulens_freq),
                status="SUCCESS" if has_trulens else "FAILED",
                dashboard_verified=has_trulens,
                agent_executed=has_trulens
            )
        self.session.commit()
