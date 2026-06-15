"""Validation Service — dynamic validation metrics registry, rule evaluation, and audit logging.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from sqlalchemy.orm import Session

from store import repo
from store.models import AgentValidationValueRow, AgentValidationRuleRow, ValidationMetricRow

logger = logging.getLogger("dpi_ls.validation_service")

# Standard Validation Metric definitions per requirements
STANDARD_METRICS = [
    ("accuracy", "Accuracy Score", "accuracy", "Semantic accuracy compared to ground-truth answers", "LLM-as-Judge / TruLens"),
    ("completeness", "Completeness Score", "completeness", "Missing information detection and coverage", "Recall Harness / Pydantic"),
    ("consistency", "Consistency Score", "consistency", "Repeatability and variance of outputs", "SME Flow / Human Feedback"),
    ("reliability", "Reliability Score", "reliability", "Failure rate and execution stability", "Postman / Exception Trackers"),
    ("groundedness", "Groundedness Score", "groundedness", "Response groundedness compared to source context", "RAGAS / DeepEval"),
    ("hallucination_detection", "Hallucination Detection", "hallucination", "Groundedness and unsupported claims checks", "DeepEval / RAGAS"),
    ("user_feedback", "User Feedback Rating", "user_feedback", "Thumbs up/down, ratings, and human review sign-offs", "DPI-LS SME Ratings Table"),
    ("success_rate", "Operational Success Rate", "operational", "Success rate of automated agent executions", "APM logs / CloudWatch"),
    ("error_rate", "Operational Error Rate", "operational", "Failure and error tracking metrics", "APM logs / CloudWatch"),
    ("outcome_achievement", "Outcome Achievement", "business", "Task resolution and business objective completion rate", "ServiceNow / MasterControl"),
]


def register_standard_metrics(s: Session) -> None:
    """Pre-populate the database with the standard 10 validation metrics."""
    for metric_id, name, category, description, source in STANDARD_METRICS:
        repo.save_validation_metric(
            s=s,
            metric_id=metric_id,
            metric_name=name,
            category=category,
            description=description,
            source_system=source,
        )
    logger.info("Registered standard validation metric definitions.")


class ValidationService:
    """Orchestrates dynamic rule evaluations, audit logging, and scoring integration."""

    @staticmethod
    def evaluate_validation(
        s: Session,
        agent_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Evaluate agent validation rules against recorded values in a given period."""
        # 1. Fetch rules and validation values
        rules = [r for r in repo.list_agent_validation_rules(s, agent_id) if r.enabled]
        values = repo.list_agent_validation_values(s, agent_id, period_start, period_end)

        if not rules:
            # Vacuous default: if no validation rules are configured, validation is 1.0 (100% compliant)
            audit_msg = (
                f"[AUDIT LOG] Validation calculation for agent '{agent_id}' from {period_start} to {period_end}:\n"
                f"  - No active validation rules configured. Triggering vacuous safe default.\n"
                f"  - Validation Score: 1.0"
            )
            logger.info(audit_msg)
            return {
                "agent_id": agent_id,
                "validation_score": 1.0,
                "validated_components": 0,
                "required_components": 0,
                "rules_evaluated": [],
            }

        # Group values by metric_id
        metric_values: dict[str, list[float]] = {}
        for v in values:
            metric_values.setdefault(v.metric_id, []).append(v.value)

        rules_passed = 0
        rules_evaluated = []

        # 2. Evaluate each rule
        for rule in rules:
            vals = metric_values.get(rule.metric_id, [])
            if not vals:
                # Rule is configured, but no run data exists for this period. Mark as failed.
                avg_val = 0.0
                passed = False
            else:
                avg_val = sum(vals) / len(vals)
                if rule.operator == "gte":
                    passed = avg_val >= rule.threshold
                elif rule.operator == "lte":
                    passed = avg_val <= rule.threshold
                elif rule.operator == "eq":
                    passed = abs(avg_val - rule.threshold) < 1e-6
                else:
                    passed = False

            if passed:
                rules_passed += 1

            rules_evaluated.append({
                "metric_id": rule.metric_id,
                "operator": rule.operator,
                "threshold": rule.threshold,
                "average_value": avg_val,
                "passed": passed,
                "run_count": len(vals),
            })

        validation_score = rules_passed / len(rules)

        # 3. Write structured audit log
        audit_msg = (
            f"[AUDIT LOG] Validation calculation for agent '{agent_id}' from {period_start} to {period_end}:\n"
            f"  - Active Rules: {len(rules)}\n"
            f"  - Rules Passed: {rules_passed}\n"
            f"  - Validation Score: {validation_score:.4f}\n"
            f"  - Evaluations: {rules_evaluated}"
        )
        logger.info(audit_msg)

        return {
            "agent_id": agent_id,
            "validation_score": validation_score,
            "validated_components": rules_passed,
            "required_components": len(rules),
            "rules_evaluated": rules_evaluated,
        }
