"""Risk Incident Engine.

Responsible for normalizing runtime events into Risk incidents
and calculating the mathematical Risk (R) formula:
R = 1 - min(1, Σ(Frequency × Severity) / Rmax)
"""

from typing import Dict, Any, List, Optional
import uuid
import datetime

class RiskIncident:
    def __init__(
        self,
        name: str,
        category: str,
        source_resource: str,
        severity: str,
        severity_weight: float,
        frequency: int,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        self.incident_id = str(uuid.uuid4())
        self.name = name
        self.category = category
        self.source_resource = source_resource
        self.severity = severity
        self.severity_weight = severity_weight
        self.frequency = frequency
        self.risk_contribution = frequency * severity_weight
        self.trace_id = trace_id
        self.span_id = span_id
        self.correlation_id = correlation_id
        self.timestamp = datetime.datetime.utcnow().isoformat()
        self.status = "NORMALIZED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "name": self.name,
            "category": self.category,
            "source_resource": self.source_resource,
            "severity": self.severity,
            "severity_weight": self.severity_weight,
            "frequency": self.frequency,
            "risk_contribution": self.risk_contribution,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "status": self.status,
        }

class RiskFormulaEngine:
    def __init__(self, rmax: float = 100.0):
        self.rmax = rmax

    def calculate_risk(self, incidents: List[RiskIncident]) -> Dict[str, Any]:
        total_risk = sum(inc.risk_contribution for inc in incidents)
        
        # Formula: R = 1 - min(1, Σ(Frequency × Severity) / Rmax)
        risk_score = 1.0 - min(1.0, total_risk / self.rmax)
        
        return {
            "total_risk": total_risk,
            "rmax": self.rmax,
            "risk_score": max(0.0, risk_score),
            "incidents_count": len(incidents),
            "critical_incidents": sum(1 for i in incidents if i.severity == "CRITICAL"),
            "high_incidents": sum(1 for i in incidents if i.severity == "HIGH"),
            "medium_incidents": sum(1 for i in incidents if i.severity == "MEDIUM"),
            "low_incidents": sum(1 for i in incidents if i.severity == "LOW")
        }

def normalize_incident(raw_event: Dict[str, Any], resource_name: str) -> RiskIncident:
    """Normalize a raw resource event into a standardized RiskIncident."""
    # Mappings based on resource
    severity_map = {
        "critical": 10.0,
        "high": 5.0,
        "medium": 2.0,
        "low": 0.5
    }
    
    severity_str = raw_event.get("severity", "medium").lower()
    severity_weight = severity_map.get(severity_str, 1.0)
    
    return RiskIncident(
        name=raw_event.get("name", "Unknown Event"),
        category=raw_event.get("category", "General"),
        source_resource=resource_name,
        severity=severity_str.upper(),
        severity_weight=severity_weight,
        frequency=raw_event.get("frequency", 1),
        trace_id=raw_event.get("trace_id"),
        span_id=raw_event.get("span_id"),
        correlation_id=raw_event.get("correlation_id")
    )
