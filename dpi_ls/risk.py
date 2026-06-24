"""LLM-Guard integration for the R (risk) dimension.

This module uses local llm-guard scanners to detect prompt injections, jailbreaks,
toxicity, and PII in raw text. It maps the detections to numerical severity weights
(1.0 to 0.2) for the DPI telemetry engine.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dotenv import load_dotenv
load_dotenv(override=True)
import threading
import warnings
import concurrent.futures
import copy

logger = logging.getLogger(__name__)

# Set local HuggingFace cache directory
os.environ["HF_HOME"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hf_cache"))


# Suppress noisy warnings
warnings.filterwarnings("ignore", message="Entity CUSTOM doesn't have the corresponding recognizer")
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
logging.getLogger("llm_guard").setLevel(logging.WARNING)

HAS_LLM_GUARD = False
input_scanners = []
output_scanners = []
vault = None
_init_lock = threading.Lock()

_scan_cache = {}
_cache_lock = threading.Lock()
_CACHE_SIZE = 1000
_CACHE_ENABLED = os.getenv("DPI_CACHE_RISK_SCANS", "1") == "1"

_eager_init_started = False
_scanner_executor = concurrent.futures.ThreadPoolExecutor(max_workers=14, thread_name_prefix="dpi_scanner")

_RISK_NAMES = {
    "Anonymize": "PiiAnonymizationViolation",
    "PromptInjection": "PromptInjectionAttack",
    "Jailbreak": "JailbreakSafetyBypass",
    "Toxicity": "ToxicHarmfulLanguage",
    "Sentiment": "HostileSentimentDetected",
    "TokenLimit": "TokenLimitExceeded",
    "BanSubstrings": "BannedSubstringFound",
    "BanTopics": "BannedTopicDetected",
    "Code": "CodeInjectionMaliciousCode",
    "Sensitive": "DataLeakagePiiExposure",
    "Deanonymize": "DeanonymizationReidentification",
    "NoRefusal": "RefusalBypassDetected",
    "Relevance": "ResponseNotRelevant",
    "OutputToxicity": "ToxicOutput",
    "OutputCode": "MaliciousCodeInOutput",
    "OutputBanTopics": "BannedTopicInOutput",
    "OutputBanSubstrings": "BannedSubstringInOutput",
}

_SEVERITY_MAPPING = {
    "PromptInjection": 1.0,
    "Jailbreak": 1.0,
    "Code": 1.0,
    "BanSubstrings": 1.0,
    "Anonymize": 0.6,
    "Toxicity": 0.6,
    "Sentiment": 0.6,
    "BanTopics": 0.6,
    "TokenLimit": 0.2,
    "Sensitive": 1.0,
    "Deanonymize": 1.0,
    "OutputCode": 1.0,
    "OutputBanSubstrings": 1.0,
    "OutputToxicity": 0.6,
    "OutputBanTopics": 0.6,
    "NoRefusal": 0.6,
    "Relevance": 0.2,
}

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def _get_cached_scan(cache_key: str) -> list[dict] | None:
    if not _CACHE_ENABLED:
        return None
    with _cache_lock:
        cached = _scan_cache.get(cache_key)
        if cached is not None:
            return copy.deepcopy(cached)
        return None

def _set_cached_scan(cache_key: str, incidents: list[dict]) -> None:
    if not _CACHE_ENABLED:
        return
    with _cache_lock:
        _scan_cache[cache_key] = copy.deepcopy(incidents)
        if len(_scan_cache) > _CACHE_SIZE:
            first_key = next(iter(_scan_cache))
            del _scan_cache[first_key]
            logger.debug(f"Cache evicted oldest entry, size now {len(_scan_cache)}")

def _init_scanners():
    global HAS_LLM_GUARD, input_scanners, output_scanners, vault
    if HAS_LLM_GUARD:
        return

    with _init_lock:
        if HAS_LLM_GUARD:
            return

        _init_scanners_unsafe()


def eager_init():
    """Pre-load all LLM Guard scanner models in a background thread.

    Call this at ``dpi_ls.monitor()`` time so all models are fully loaded
    into memory before the first scenario runs.  Every subsequent call to
    ``scan_llmguard_input_risks`` / ``scan_llmguard_output_risks`` then
    finds ``HAS_LLM_GUARD = True`` and goes straight to ``.scan()`` on
    the already-instantiated scanner objects — no model loading at all.
    """
    global _eager_init_started
    if HAS_LLM_GUARD:
        return  # already loaded, nothing to do
        
    with _init_lock:
        if _eager_init_started:
            return
        _eager_init_started = True
        
    threading.Thread(
        target=_init_scanners,
        daemon=True,
        name="dpi_risk_eager_init",
    ).start()
    logger.info("DPI-LS Risk Scanner: eager model pre-load started in background.")

def _init_scanners_unsafe():
    global HAS_LLM_GUARD, input_scanners, output_scanners, vault
    try:
        import llm_guard.input_scanners.prompt_injection as pi
        pi._model_path = "protectai/deberta-v3-base-prompt-injection"

        from llm_guard.input_scanners import (
            Anonymize, PromptInjection, Jailbreak, Toxicity,
            Sentiment, TokenLimit, BanSubstrings, BanTopics
        )

        # INPUT SCANNERS - build list, then append all at once to avoid partial state
        _input = []
        try:
            from llm_guard.vault import Vault
            class DummyVault(Vault):
                def append(self, *args, **kwargs): pass
                def extend(self, *args, **kwargs): pass
            
            vault = DummyVault()
            _input.append(Anonymize(vault))
        except Exception as e:
            logger.debug(f"llm-guard Anonymize failed: {e}")

        for name, cls, kwargs in [
            ("PromptInjection", PromptInjection, {"threshold": 0.5}),
            ("Toxicity", Toxicity, {}),
            ("Sentiment", Sentiment, {"threshold": -0.6}),
            ("TokenLimit", TokenLimit, {}),
        ]:
            try:
                scanner = cls(**kwargs)
                if name == "PromptInjection":
                    scanner._tokenizer.model_max_length = 512
                _input.append(scanner)
            except Exception as e:
                logger.debug(f"llm-guard {name} failed: {e}")

        try:
            _input.append(Jailbreak(threshold=0.6))
        except Exception as e:
            logger.debug(f"llm-guard Jailbreak failed: {e}")

        try:
            _input.append(BanSubstrings(substrings=["password", "secret", "api_key", "credit_card", "ssn", "private_key", "confidential"]))
        except Exception as e:
            logger.debug(f"llm-guard BanSubstrings failed: {e}")

        try:
            _input.append(BanTopics(topics=["violence", "hate speech", "self-harm", "illegal acts"], threshold=0.75))
        except Exception as e:
            logger.debug(f"llm-guard BanTopics failed: {e}")

        # OUTPUT SCANNERS
        from llm_guard.output_scanners import (
            Sensitive, NoRefusal, Relevance,
            Toxicity as OutputToxicity,
            BanTopics as OutputBanTopics,
            BanSubstrings as OutputBanSubstrings,
        )

        _output = []


        for name, cls, kwargs in [
            ("Sensitive", Sensitive, {"entity_types": ["EMAIL_ADDRESS", "CREDIT_CARD", "PHONE_NUMBER", "US_BANK_NUMBER", "US_SSN", "CRYPTO", "IBAN_CODE", "IP_ADDRESS"]}),
            ("NoRefusal", NoRefusal, {}),
            ("Relevance", Relevance, {}),
            ("OutputToxicity", OutputToxicity, {}),
            ("OutputBanSubstrings", OutputBanSubstrings, {"substrings": ["password", "secret", "api_key", "credit_card", "ssn", "private_key", "confidential"]}),
        ]:
            try:
                _output.append(cls(**kwargs))
            except Exception as e:
                logger.debug(f"llm-guard {name} failed: {e}")

        try:
            _output.append(OutputBanTopics(topics=["violence", "hate speech", "self-harm", "illegal acts"], threshold=0.75))
        except Exception as e:
            logger.debug(f"llm-guard OutputBanTopics failed: {e}")

        # Pre-warm all scanners with a dummy scan to force lazy model weights
        # into memory BEFORE any real scan job can start.  This must happen
        # BEFORE HAS_LLM_GUARD is set so that scan threads blocked on the lock
        # (or checking the flag) cannot start real scans until pre-warm is done.
        _warmup_text = "test"
        for scanner in _input:
            try:
                scanner.scan(_warmup_text)
            except Exception:
                pass

        for scanner in _output:
            try:
                scanner.scan("", _warmup_text)
            except Exception:
                pass

        # Atomic commit: publish scanners and flip the flag only AFTER pre-warm.
        # Any thread that checked HAS_LLM_GUARD=False and is now waiting on
        # _init_lock will see HAS_LLM_GUARD=True on the inner check and return
        # immediately.  Any thread that arrives fresh will see HAS_LLM_GUARD=True
        # on the outer (lock-free) check and also return immediately.
        # Either way, the first real .scan() call always hits a warm model.
        input_scanners.clear()
        input_scanners.extend(_input)
        output_scanners.clear()
        output_scanners.extend(_output)
        HAS_LLM_GUARD = True

        logger.info(
            f"DPI-LS Risk Scanner: [READY] ALL MODELS LOADED - "
            f"{len(input_scanners)} input scanners "
            f"({', '.join(s.__class__.__name__ for s in input_scanners)}) + "
            f"{len(output_scanners)} output scanners "
            f"({', '.join(s.__class__.__name__ for s in output_scanners)}). "
            f"Ready to invoke on every scenario."
        )
    except ImportError:
        logger.warning("llm-guard not installed. Risk detection disabled.")


def scan_llmguard_input_risks(prompt: str) -> list[dict]:
    """Scan input prompt with caching and conditional expensive models."""
    if not prompt or not prompt.strip():
        return []

    cache_key = f"input:{_hash_text(prompt)}"
    cached = _get_cached_scan(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit: {cache_key[:8]}...")
        return cached

    _init_scanners()

    if not HAS_LLM_GUARD or not input_scanners:
        logger.warning("DPI-LS Risk Scanner: models not loaded yet — skipping input scan.")
        return []

    snippet = prompt[:80].replace("\n", " ")
    scanner_names = [s.__class__.__name__ for s in input_scanners]
    logger.info(
        f"DPI-LS Risk [INPUT SCAN] -> invoking {len(input_scanners)} loaded models "
        f"({', '.join(scanner_names)}) - prompt: '{snippet}...'"
    )

    incidents = []

    def _run_scanner(scanner):
        try:
            result_tuple = scanner.scan(prompt)
            if len(result_tuple) == 2:
                _, is_valid = result_tuple
            else:
                _, is_valid, _ = result_tuple

            if not is_valid:
                scanner_name = scanner.__class__.__name__
                risk_name = _RISK_NAMES.get(scanner_name, scanner_name)
                severity = _SEVERITY_MAPPING.get(scanner_name, 0.6)
                return {
                    "severity_weight": severity,
                    "frequency": 1,
                    "source": f"llmguard:{scanner_name.lower()}",
                    "risk_name": risk_name,
                }
        except Exception as e:
            logger.debug(f"llm-guard input scanner {scanner.__class__.__name__} failed: {e}")
        return None

    futures = [_scanner_executor.submit(_run_scanner, s) for s in input_scanners]
    for future in concurrent.futures.as_completed(futures):
        res = future.result()
        if res:
            incidents.append(res)

    _set_cached_scan(cache_key, incidents)

    if incidents:
        found = [i["risk_name"] for i in incidents]
        logger.info(
            f"DPI-LS Risk [INPUT SCAN] [WARN] VIOLATIONS DETECTED: {found} - prompt: '{snippet}...'"
        )
    else:
        logger.info(
            f"DPI-LS Risk [INPUT SCAN] [OK] CLEAN (no violations) - prompt: '{snippet}...'"
        )

    return incidents


def scan_llmguard_output_risks(prompt: str, output: str) -> list[dict]:
    """Scan LLM output with caching and conditional expensive models."""
    if not output or not output.strip():
        return []

    cache_key = f"output:{_hash_text(output)}"
    cached = _get_cached_scan(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit: {cache_key[:8]}...")
        return cached

    _init_scanners()

    if not HAS_LLM_GUARD or not output_scanners:
        logger.warning("DPI-LS Risk Scanner: models not loaded yet — skipping output scan.")
        return []

    snippet = output[:80].replace("\n", " ")
    scanner_names = [s.__class__.__name__ for s in output_scanners]
    logger.info(
        f"DPI-LS Risk [OUTPUT SCAN] -> invoking {len(output_scanners)} loaded models "
        f"({', '.join(scanner_names)}) - output: '{snippet}...'"
    )

    incidents = []
    prompt = prompt or ""

    def _run_scanner(scanner):
        try:
            result_tuple = scanner.scan(prompt, output)
            if len(result_tuple) == 2:
                _, is_valid = result_tuple
            else:
                _, is_valid, _ = result_tuple

            if not is_valid:
                scanner_name = scanner.__class__.__name__
                mapped_name = scanner_name
                if mapped_name == "Toxicity":
                    mapped_name = "OutputToxicity"
                elif mapped_name == "BanTopics":
                    mapped_name = "OutputBanTopics"
                elif mapped_name == "BanSubstrings":
                    mapped_name = "OutputBanSubstrings"

                risk_name = _RISK_NAMES.get(mapped_name, mapped_name)
                severity = _SEVERITY_MAPPING.get(mapped_name, 0.6)
                return {
                    "severity_weight": severity,
                    "frequency": 1,
                    "source": f"llmguard:{mapped_name.lower()}",
                    "risk_name": risk_name,
                }
        except Exception as e:
            logger.debug(f"llm-guard output scanner {scanner.__class__.__name__} failed: {e}")
        return None

    futures = [_scanner_executor.submit(_run_scanner, s) for s in output_scanners]
    for future in concurrent.futures.as_completed(futures):
        res = future.result()
        if res:
            incidents.append(res)

    _set_cached_scan(cache_key, incidents)

    if incidents:
        found = [i["risk_name"] for i in incidents]
        logger.info(
            f"DPI-LS Risk [OUTPUT SCAN] [WARN] VIOLATIONS DETECTED: {found} - output: '{snippet}...'"
        )
    else:
        logger.info(
            f"DPI-LS Risk [OUTPUT SCAN] [OK] CLEAN (no violations) - output: '{snippet}...'"
        )

    return incidents
