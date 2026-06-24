"""Presidio-based policy scanner for the G (governance) dimension.

This replaces the old regex-based scanner. It uses Microsoft Presidio
to automatically detect Data Leakage (PII) in agent outputs.

If presidio-analyzer is installed, it scans the text and returns a set
of raw entity types (e.g. 'CREDIT_CARD', 'US_SSN') that it found.
If not installed, it safely returns an empty set so the engine doesn't crash.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dotenv import load_dotenv
load_dotenv(override=True)
import re
import time
import json
import httpx
import threading
from typing import Any

log = logging.getLogger(__name__)

# Policy scanning cache (same as risk.py)
_policy_cache = {}
_policy_cache_lock = threading.Lock()
_POLICY_CACHE_SIZE = 1000
_POLICY_CACHE_ENABLED = os.getenv("DPI_CACHE_POLICY_SCANS", "1") == "1"

def _hash_text_policy(text: str) -> str:
    """Hash text for cache key."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def _get_cached_policy(cache_key: str) -> set[str] | None:
    """Get cached policy scan result."""
    if not _POLICY_CACHE_ENABLED:
        return None
    with _policy_cache_lock:
        return _policy_cache.get(cache_key)

def _set_cached_policy(cache_key: str, violations: set[str]) -> None:
    """Set cached policy scan result with LRU eviction."""
    if not _POLICY_CACHE_ENABLED:
        return
    with _policy_cache_lock:
        _policy_cache[cache_key] = violations
        if len(_policy_cache) > _POLICY_CACHE_SIZE:
            first_key = next(iter(_policy_cache))
            del _policy_cache[first_key]
            log.debug(f"Policy cache evicted oldest entry, size now {len(_policy_cache)}")

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
    Cached to prevent repeated scanning of identical text.
    """
    if not text:
        return set()

    # Check cache first
    cache_key = f"policy:{_hash_text_policy(text)}"
    cached = _get_cached_policy(cache_key)
    if cached is not None:
        log.debug(f"Policy cache hit: {cache_key[:8]}...")
        return cached

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

    # Cache result
    _set_cached_policy(cache_key, seen)
    return seen

# Backwards-compatible alias — some external callers (and the
# collector's tests) use the longer name.
_rules_for_text = scan_policy_violations


# ============================================================================
# Semantic Tool Policy Scanner (RAG-based) & OPA Scanner
# ============================================================================

HAS_SEMANTIC_SCANNER = False
semantic_db_client = None
semantic_collection = None
semantic_encoder = None
SEMANTIC_THRESHOLD = 0.45
_SEMANTIC_CACHE: dict[tuple[str, str], float] = {}
_semantic_lock = threading.Lock()

HAS_OPA_SCANNER = False
OPA_ENDPOINT = None

def init_opa_scanner(endpoint: str = "http://localhost:8181/v1/data/dpi_ls/violations"):
    global HAS_OPA_SCANNER, OPA_ENDPOINT
    OPA_ENDPOINT = endpoint
    HAS_OPA_SCANNER = True
    log.info(f"DPI-LS Policy Scanner: OPA Scanner initialized at {endpoint}")

def init_semantic_scanner(db_path: str):
    global HAS_SEMANTIC_SCANNER, semantic_db_client, semantic_collection, semantic_encoder
    if HAS_SEMANTIC_SCANNER:
        return

    with _semantic_lock:
        if HAS_SEMANTIC_SCANNER:
            return

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            
            log.info(f"DPI-LS Policy Scanner: Initializing Semantic RAG from {db_path}...")
            semantic_db_client = chromadb.PersistentClient(path=db_path)
            semantic_collection = semantic_db_client.get_collection(name="governance_rules")
            
            semantic_encoder = SentenceTransformer("all-MiniLM-L6-v2")
            HAS_SEMANTIC_SCANNER = True
            log.info("DPI-LS Policy Scanner: Semantic RAG Engine successfully loaded.")
        except Exception as e:
            log.warning(f"DPI-LS Policy Scanner: Failed to initialize semantic scanner: {e}")

def _get_semantic_model():
    global semantic_encoder
    if semantic_encoder is None:
        with _semantic_lock:
            if semantic_encoder is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    semantic_encoder = SentenceTransformer("all-MiniLM-L6-v2")
                except ImportError:
                    pass
    return semantic_encoder

def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())

def _semantic_similarity(a: str, b: str) -> float:
    model = _get_semantic_model()
    if model is None: return 0.0
    cache_key = (min(a, b), max(a, b))
    if cache_key in _SEMANTIC_CACHE:
        return _SEMANTIC_CACHE[cache_key]
    from sentence_transformers import util
    embeddings = model.encode([a, b], convert_to_tensor=True)
    score = float(util.cos_sim(embeddings[0], embeddings[1]))
    _SEMANTIC_CACHE[cache_key] = score
    return score

def resolve_field(field_path: str, aliases: list[str], args: dict, context: dict) -> tuple[Any, str]:
    source = {**args, **context}
    
    if field_path.startswith("args."):
        bare = field_path[5:]
    elif field_path.startswith("context."):
        bare = field_path[8:]
    else:
        bare = field_path

    norm_bare = _normalize(bare)

    if bare in source:
        return source[bare], "exact"

    for key, val in source.items():
        if _normalize(key) == norm_bare:
            return val, "normalized"

    model = _get_semantic_model()
    if model is not None:
        start_time = time.perf_counter()
        best_score = 0.0
        best_val = None
        best_match_key = None
        for key, val in source.items():
            score = _semantic_similarity(bare, key)
            if score > best_score:
                best_score = score
                best_val = val
                best_match_key = key
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if best_score >= SEMANTIC_THRESHOLD:
            log.debug(f"    [TIMER] Semantic match: '{bare}' ~ '{best_match_key}' ({best_score:.2f}) took {elapsed_ms:.2f} ms")
            return best_val, f"semantic({best_score:.2f})"

    for alias in (aliases or []):
        norm_alias = _normalize(alias)
        for key, val in source.items():
            if _normalize(key) == norm_alias:
                return val, f"alias({alias})"

    return None, "miss"

def apply_operator(value: Any, op: str, expected: Any) -> bool:
    if value is None:
        if op == "is_false": return True
        if op == "is_true": return False
        return False
    try:
        if op == "eq": return value == expected
        if op == "neq": return value != expected
        if op == "gt": return float(value) > float(expected)
        if op == "lt": return float(value) < float(expected)
        if op == "gte": return float(value) >= float(expected)
        if op == "lte": return float(value) <= float(expected)
        if op == "in": return value in expected
        if op == "not_in": return value not in expected
        if op == "contains": return str(expected).lower() in str(value).lower()
        if op == "is_true": return bool(value) is True
        if op == "is_false": return bool(value) is False
    except: pass
    return False

def evaluate_condition(node: dict, args: dict, context: dict) -> bool:
    if "all" in node:
        return all(evaluate_condition(child, args, context) for child in node["all"])
    if "any" in node:
        return any(evaluate_condition(child, args, context) for child in node["any"])

    field_path = node.get("field", "")
    aliases = node.get("aliases", [])
    op = node.get("op", "eq")
    expected = node.get("value")

    val, layer = resolve_field(field_path, aliases, args, context)

    if val is None:
        return False
        
    if isinstance(val, str) and op in ["gt", "lt", "gte", "lte"]:
        try:
            val = float(val)
        except ValueError:
            pass
    
    if isinstance(val, str) and op in ["is_true", "is_false"]:
        if val.lower() == "true": val = True
        elif val.lower() == "false": val = False

    return apply_operator(val, op, expected)

def scan_tool_policy_violations(tool_name: str, args: dict, context: dict) -> set[str]:
    """Evaluates the semantic RAG policy guardrails.
    Returns the set of triggered policy action names.
    """
    violations = set()
    
    if HAS_SEMANTIC_SCANNER and semantic_collection is not None:
        try:
            results = semantic_collection.query(query_texts=[tool_name], n_results=50)
            if results["distances"] and results["distances"][0]:
                distance_threshold = 1.0 - SEMANTIC_THRESHOLD
                for i, distance in enumerate(results["distances"][0]):
                    if distance <= distance_threshold:
                        matched_action = results["documents"][0][i]
                        raw_policy_str = results["metadatas"][0][i]["raw_policy"]
                        policy = json.loads(raw_policy_str)
                        
                        when = policy.get("when", {})
                        if when and evaluate_condition(when, args, context):
                            violations.add(matched_action)
        except Exception as e:
            log.warning(f"Semantic RAG query failed: {e}")
            
    if HAS_OPA_SCANNER and OPA_ENDPOINT:
        try:
            payload = {
                "input": {
                    "tool_name": tool_name,
                    "args": args,
                    "context": context
                }
            }
            resp = httpx.post(OPA_ENDPOINT, json=payload, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if "result" in data and isinstance(data["result"], list):
                    for v in data["result"]:
                        violations.add(v)
            else:
                log.warning(f"OPA scanner query failed with status {resp.status_code}: {resp.text}")
        except httpx.ConnectError:
            log.debug(f"OPA scanner offline: {OPA_ENDPOINT} not reachable.")
        except Exception as e:
            log.warning(f"OPA scanner query failed: {e}")
            
    return violations
