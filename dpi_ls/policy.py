"""Presidio-based policy scanner for the G (governance) dimension.

This replaces the old regex-based scanner. It uses Microsoft Presidio
to automatically detect Data Leakage (PII) in agent outputs.

If presidio-analyzer is installed, it scans the text and returns a set
of raw entity types (e.g. 'CREDIT_CARD', 'US_SSN') that it found.
If not installed, it safely returns an empty set so the engine doesn't crash.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

HAS_PRESIDIO = False
analyzer = None

try:
    from presidio_analyzer import AnalyzerEngine
    HAS_PRESIDIO = True
    analyzer = AnalyzerEngine()
    log.info("DPI-LS Policy Scanner: Using Presidio NLP Engine.")
except ImportError:
    log.debug("DPI-LS Policy Scanner: presidio-analyzer not installed. Governance detection disabled.")

def scan_policy_violations(text: str) -> set[str]:
    """Return the set of raw Presidio entity types found in ``text``.

    Always returns a real set so callers can iterate, ``len()``, or
    compare with ``==`` against the empty set.
    """
    if not text:
        return set()
        
    seen: set[str] = set()
    
    if HAS_PRESIDIO and analyzer is not None:
        try:
            # We omit the 'entities' parameter to scan for all supported types natively
            results = analyzer.analyze(text=text, language='en')
            for result in results:
                # Only flag high-confidence matches as violations to keep false-positives low
                if result.score > 0.6:
                    seen.add(result.entity_type)
        except Exception as e:
            log.warning("Presidio analysis failed: %s", e)
            
    return seen

# Backwards-compatible alias — some external callers (and the
# collector's tests) use the longer name.
_rules_for_text = scan_policy_violations
