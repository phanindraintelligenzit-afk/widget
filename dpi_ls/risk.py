"""LLM-Guard integration for the R (risk) dimension.

This module uses local llm-guard scanners to detect prompt injections, jailbreaks,
toxicity, and PII in raw text. It maps the detections to numerical severity weights
(1.0 to 0.2) for the DPI telemetry engine.
"""

from __future__ import annotations

import logging
import os
import threading
import warnings

logger = logging.getLogger(__name__)

# Set local HuggingFace cache directory
os.environ["HF_HOME"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hf_cache"))
os.environ["HF_HUB_OFFLINE"] = "1" # Forces lightning-fast local loading
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Suppress noisy warnings
warnings.filterwarnings("ignore", message="Entity CUSTOM doesn't have the corresponding recognizer")
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
logging.getLogger("llm_guard").setLevel(logging.WARNING)

HAS_LLM_GUARD = False
input_scanners = []
output_scanners = []
vault = None
_init_lock = threading.Lock()

# Severity mapping
_SEVERITY_MAPPING = {
    # Input
    "PromptInjection": 1.0,
    "Jailbreak": 1.0,
    "Code": 1.0,
    "BanSubstrings": 1.0,
    "Anonymize": 0.6,
    "Toxicity": 0.6,
    "Sentiment": 0.6,
    "BanTopics": 0.6,
    "TokenLimit": 0.2,

    # Output
    "Sensitive": 1.0,
    "Deanonymize": 1.0,
    "OutputCode": 1.0,
    "OutputBanSubstrings": 1.0,
    "OutputToxicity": 0.6,
    "OutputBanTopics": 0.6,
    "NoRefusal": 0.6,
    "Relevance": 0.2,
}

def _init_scanners():
    global HAS_LLM_GUARD, input_scanners, output_scanners, vault
    if HAS_LLM_GUARD:
        return

    with _init_lock:
        if HAS_LLM_GUARD:
            return

    try:
        import llm_guard.input_scanners.prompt_injection as pi
        pi._model_path = "protectai/deberta-v3-base-prompt-injection"
        
        from llm_guard.input_scanners import (
            Anonymize, PromptInjection, Jailbreak, Toxicity,
            Sentiment, TokenLimit, BanSubstrings, BanTopics
        )

        try:
            from llm_guard.vault import Vault
            vault = Vault()
            input_scanners.append(Anonymize(vault))
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
                input_scanners.append(scanner)
            except Exception as e:
                logger.debug(f"llm-guard {name} failed: {e}")

        try:
            input_scanners.append(Jailbreak(threshold=0.6))
        except Exception as e:
            logger.debug(f"llm-guard Jailbreak failed: {e}")

        try:
            input_scanners.append(BanSubstrings(substrings=["password", "secret", "api_key", "credit_card", "ssn", "private_key", "confidential"]))
        except Exception as e:
            logger.debug(f"llm-guard BanSubstrings failed: {e}")

        try:
            input_scanners.append(BanTopics(topics=["violence", "hate speech", "self-harm", "illegal acts"], threshold=0.75))
        except Exception as e:
            logger.debug(f"llm-guard BanTopics failed: {e}")

        # OUTPUT SCANNERS
        from llm_guard.output_scanners import (
            Deanonymize, Sensitive, NoRefusal, Relevance,
            Toxicity as OutputToxicity,
            BanTopics as OutputBanTopics,
            BanSubstrings as OutputBanSubstrings,
        )

        if vault:
            try:
                output_scanners.append(Deanonymize(vault))
            except Exception as e:
                logger.debug(f"llm-guard Deanonymize failed: {e}")

        for name, cls, kwargs in [
            ("Sensitive", Sensitive, {"entity_types": ["EMAIL_ADDRESS", "CREDIT_CARD", "PHONE_NUMBER", "US_BANK_NUMBER", "US_SSN", "CRYPTO", "IBAN_CODE", "IP_ADDRESS"]}),
            ("NoRefusal", NoRefusal, {}),
            ("Relevance", Relevance, {}),
            ("OutputToxicity", OutputToxicity, {}),
            ("OutputBanSubstrings", OutputBanSubstrings, {"substrings": ["password", "secret", "api_key", "credit_card", "ssn", "private_key", "confidential"]}),
        ]:
            try:
                output_scanners.append(cls(**kwargs))
            except Exception as e:
                logger.debug(f"llm-guard {name} failed: {e}")

        try:
            output_scanners.append(OutputBanTopics(topics=["violence", "hate speech", "self-harm", "illegal acts"], threshold=0.75))
        except Exception as e:
            logger.debug(f"llm-guard OutputBanTopics failed: {e}")

        HAS_LLM_GUARD = True
        logger.info(f"DPI-LS Risk Scanner: llm-guard initialized with {len(input_scanners)} input and {len(output_scanners)} output scanners.")
    except ImportError:
        logger.warning("llm-guard not installed. Risk detection disabled.")


def scan_llmguard_input_risks(prompt: str) -> list[dict]:
    """Scan input prompt using local llm-guard and return a list of risk incidents."""
    if not prompt or not prompt.strip():
        return []
        
    _init_scanners()
    
    if not HAS_LLM_GUARD or not input_scanners:
        return []
        
    incidents = []
    
    for scanner in input_scanners:
        try:
            result_tuple = scanner.scan(prompt)
            if len(result_tuple) == 2:
                _, is_valid = result_tuple
            else:
                _, is_valid, _ = result_tuple
                
            if not is_valid:
                scanner_name = scanner.__class__.__name__
                severity = _SEVERITY_MAPPING.get(scanner_name, 0.6)
                incidents.append({
                    "severity_weight": severity,
                    "frequency": 1,
                    "source": f"llmguard:{scanner_name.lower()}"
                })
        except Exception as e:
            logger.debug(f"llm-guard input scanner {scanner.__class__.__name__} failed during scan: {e}")
            
    return incidents


def scan_llmguard_output_risks(prompt: str, output: str) -> list[dict]:
    """Scan LLM output using local llm-guard and return a list of risk incidents."""
    if not output or not output.strip():
        return []
        
    _init_scanners()
    
    if not HAS_LLM_GUARD or not output_scanners:
        return []
        
    incidents = []
    # If the prompt is missing for some reason, use an empty string so output scanners don't crash
    prompt = prompt or ""
    
    for scanner in output_scanners:
        try:
            result_tuple = scanner.scan(prompt, output)
            if len(result_tuple) == 2:
                _, is_valid = result_tuple
            else:
                _, is_valid, _ = result_tuple
                
            if not is_valid:
                scanner_name = scanner.__class__.__name__
                # Handle aliased scanner names
                mapped_name = scanner_name
                if mapped_name == "Toxicity":
                    mapped_name = "OutputToxicity"
                elif mapped_name == "BanTopics":
                    mapped_name = "OutputBanTopics"
                elif mapped_name == "BanSubstrings":
                    mapped_name = "OutputBanSubstrings"

                severity = _SEVERITY_MAPPING.get(mapped_name, 0.6)
                incidents.append({
                    "severity_weight": severity,
                    "frequency": 1,
                    "source": f"llmguard:{mapped_name.lower()}"
                })
        except Exception as e:
            logger.debug(f"llm-guard output scanner {scanner.__class__.__name__} failed during scan: {e}")
            
    return incidents
