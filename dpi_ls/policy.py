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
    log.debug("DPI-LS Policy Scanner: presidio-analyzer not installed. PII detection disabled.")

HAS_DETECT_SECRETS = False
secrets_plugins = []

try:
    from detect_secrets.plugins.aws import AWSKeyDetector
    from detect_secrets.plugins.slack import SlackDetector
    from detect_secrets.plugins.private_key import PrivateKeyDetector
    from detect_secrets.plugins.basic_auth import BasicAuthDetector
    from detect_secrets.plugins.jwt import JwtTokenDetector
    HAS_DETECT_SECRETS = True
    secrets_plugins = [
        AWSKeyDetector(),
        SlackDetector(),
        PrivateKeyDetector(),
        BasicAuthDetector(),
        JwtTokenDetector()
    ]
    log.info("DPI-LS Policy Scanner: Using detect-secrets engine.")
except ImportError:
    log.debug("DPI-LS Policy Scanner: detect-secrets not installed. Secrets detection disabled.")

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
            
    if HAS_DETECT_SECRETS:
        for plugin in secrets_plugins:
            try:
                # analyze_string yields the matched string value itself, not an object
                for secret_match in plugin.analyze_string(text):
                    seen.add(type(plugin).__name__)
            except Exception as e:
                log.warning("detect-secrets plugin %s failed: %s", type(plugin).__name__, e)
            
    return seen

# Backwards-compatible alias — some external callers (and the
# collector's tests) use the longer name.
_rules_for_text = scan_policy_violations
