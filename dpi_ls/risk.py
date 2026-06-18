"""Lakera Guard integration for the R (risk) dimension.

This module calls the Lakera Guard API to detect prompt injections, jailbreaks,
toxicity, and PII in raw text. It maps Lakera's confidence levels (l1 to l5)
into numerical severity weights (1.0 to 0.2) for the DPI telemetry engine.
"""

from __future__ import annotations

import logging
import os
import requests

logger = logging.getLogger(__name__)

# Severity mapping based on Lakera confidence levels
_CONFIDENCE_TO_SEVERITY = {
    "l1_confident": 1.0,
    "l2_very_likely": 0.8,
    "l3_likely": 0.6,
    "l4_less_likely": 0.4,
    "l5_unlikely": 0.2,
}

def scan_lakera_risks(text: str) -> list[dict]:
    """Scan text using Lakera Guard and return a list of risk incidents.
    
    Returns a list of dicts:
    [{"severity_weight": float, "frequency": int, "source": str}]
    """
    if not text or not text.strip():
        return []
        
    api_key = os.getenv("LAKERA_API_KEY")
    if not api_key:
        return []
        
    url = "https://api.lakera.ai/v2/guard"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [{"role": "user", "content": text}],
        "breakdown": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("flagged"):
            return []
            
        incidents = []
        for b in data.get("breakdown", []):
            if b.get("detected"):
                threat_type = b.get("detector_type", "unknown_threat")
                confidence = b.get("result", "l5_unlikely")
                severity = _CONFIDENCE_TO_SEVERITY.get(confidence, 0.2)
                
                incidents.append({
                    "severity_weight": severity,
                    "frequency": 1,
                    "source": f"lakera:{threat_type}"
                })
        return incidents
    except Exception as e:
        logger.debug(f"Lakera risk scan failed: {e}")
        return []
