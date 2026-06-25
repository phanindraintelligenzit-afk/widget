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
import urllib.request
import urllib.parse
import json
import io
import yaml
from pathlib import Path

# Try to import pandas, chromadb, and sentence_transformers
try:
    import pandas as pd
    import chromadb
    from sentence_transformers import SentenceTransformer
    HAS_HEURISTICS = True
except ImportError:
    HAS_HEURISTICS = False

logger = logging.getLogger(__name__)

# Suppress noisy warnings
warnings.filterwarnings("ignore", message="Entity CUSTOM doesn't have the corresponding recognizer")
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
logging.getLogger("llm_guard").setLevel(logging.WARNING)

HAS_LLM_GUARD = False
input_scanners = []
output_scanners = []
vault = None
_init_lock = threading.Lock()

# --- HEURISTIC SCANNER GLOBALS ---
chroma_client = None
chroma_collection = None
sentence_encoder = None

# Point to the existing examples/risk_dimension directory to reuse the downloaded yaml and ChromaDB
CACHE_DIR = Path(__file__).parent.parent / "examples" / "risk_dimension"
POLICIES_DIR = CACHE_DIR / "policies"
DB_DIR = CACHE_DIR / "chroma_db"
DISTANCE_THRESHOLD = 0.50

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

# Heuristic/semantic engine names (more descriptive than raw tech names)
_HEURISTIC_SOURCE_NAMES = {
    "chromadb": "vectorSearch",
    "semantic": "semanticSimilarity",
    "opa": "policyEngine",
    "rebuff": "adversarialDetection",
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
    global chroma_client, chroma_collection, sentence_encoder
    
    if HAS_HEURISTICS and chroma_collection is None:
        try:
            logger.info("DPI-LS Risk Scanner: Initializing ChromaDB & SentenceTransformer for heuristic rules...")
            POLICIES_DIR.mkdir(parents=True, exist_ok=True)
            DB_DIR.mkdir(parents=True, exist_ok=True)
            
            chroma_client = chromadb.PersistentClient(path=str(DB_DIR))
            chroma_collection = chroma_client.get_or_create_collection(name="dpi_risk_signatures")
            sentence_encoder = SentenceTransformer("all-MiniLM-L6-v2")
            
            def fetch_huggingface_dataset(dataset_id, yaml_filename, risk_name, text_column, label_column=None, label_value=None):
                yaml_path = POLICIES_DIR / yaml_filename
                if yaml_path.exists():
                    return
                
                logger.info(f"DPI-LS Risk Scanner: Fetching {dataset_id} from Hugging Face API...")
                try:
                    hf_token = os.environ.get("HF_TOKEN")
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    if hf_token:
                        headers['Authorization'] = f"Bearer {hf_token}"
                    
                    api_url = f"https://datasets-server.huggingface.co/parquet?dataset={urllib.parse.quote(dataset_id, safe='')}"
                    req = urllib.request.Request(api_url, headers=headers)
                    with urllib.request.urlopen(req) as response:
                        metadata = json.loads(response.read().decode())
                        
                    urls = [file_info["url"] for file_info in metadata.get("parquet_files", [])]
                    risky_actions = []
                    
                    for url in urls:
                        req = urllib.request.Request(url, headers=headers)
                        with urllib.request.urlopen(req) as response:
                            df = pd.read_parquet(io.BytesIO(response.read()))
                            
                        for _, row in df.iterrows():
                            if label_column and label_value is not None:
                                if row.get(label_column) != label_value:
                                    continue
                            text = str(row.get(text_column, "")).strip()
                            if text:
                                risky_actions.append({"riskName": risk_name, "riskAction": text})
                    
                    with open(yaml_path, "w", encoding="utf-8") as f:
                        yaml.dump({"riskyActions": risky_actions}, f, allow_unicode=True, default_flow_style=False)
                except Exception as e:
                    logger.error(f"DPI-LS Risk Scanner: Failed to download {dataset_id}: {e}")

            # Fetch datasets
            fetch_huggingface_dataset("deepset/prompt-injections", "hf_deepset_injections.yaml", "PromptInjectionAttack", "text", "label", 1)
            fetch_huggingface_dataset("rubend18/ChatGPT-Jailbreak-Prompts", "hf_rubend18_jailbreaks.yaml", "JaiLBreakBypassDetected", "Prompt")
            fetch_huggingface_dataset("S-Labs/prompt-injection-dataset", "hf_slabs_injections.yaml", "PromptInjectionAttack", "text", "label", 1)
            
            # Load and Embed
            risky_actions = []
            for yaml_file in POLICIES_DIR.glob("*.yaml"):
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        # Use CSafeLoader if available for massive speedup
                        if hasattr(yaml, 'CSafeLoader'):
                            data = yaml.load(f, Loader=yaml.CSafeLoader)
                        else:
                            data = yaml.safe_load(f)
                        if data and "riskyActions" in data:
                            risky_actions.extend(data["riskyActions"])
                except Exception as e:
                    logger.error(f"DPI-LS Risk Scanner: Failed to read {yaml_file.name}: {e}")
                    
            documents, metadatas, ids = [], [], []
            seen_ids = set()
            for item in risky_actions:
                risk_action = item.get("riskAction")
                risk_name = item.get("riskName")
                if risk_action and risk_name:
                    doc_id = hashlib.sha256(risk_action.encode()).hexdigest()
                    if doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        documents.append(risk_action)
                        metadatas.append({"riskName": risk_name})
                        ids.append(doc_id)
            
            if documents:
                # Optimized get(): Only get IDs, not embeddings/documents, to save memory/time
                existing_data = chroma_collection.get(ids=ids, include=["metadatas"])
                existing_ids = set(existing_data["ids"])
                missing_indices = [i for i, doc_id in enumerate(ids) if doc_id not in existing_ids]
                
                if missing_indices:
                    missing_docs = [documents[i] for i in missing_indices]
                    missing_ids = [ids[i] for i in missing_indices]
                    missing_metas = [metadatas[i] for i in missing_indices]
                    logger.info(f"DPI-LS Risk Scanner: Embedding {len(missing_docs)} new signatures into ChromaDB...")
                    
                    BATCH_SIZE = 5000
                    for i in range(0, len(missing_docs), BATCH_SIZE):
                        batch_docs = missing_docs[i:i + BATCH_SIZE]
                        batch_ids = missing_ids[i:i + BATCH_SIZE]
                        batch_metas = missing_metas[i:i + BATCH_SIZE]
                        attack_embeddings = sentence_encoder.encode(batch_docs).tolist()
                        chroma_collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas, embeddings=attack_embeddings)
        except Exception as e:
            logger.error(f"DPI-LS Risk Scanner: Heuristic setup failed: {e}")

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
            
    # --- Heuristic ChromaDB Check (rebuff: vector search) ---
    if HAS_HEURISTICS and chroma_collection is not None and sentence_encoder is not None:
        try:
            prompt_embedding = sentence_encoder.encode([prompt]).tolist()
            results = chroma_collection.query(query_embeddings=prompt_embedding, n_results=1)
            if results["distances"] and results["distances"][0]:
                distance = results["distances"][0][0]
                if distance < DISTANCE_THRESHOLD:
                    risk_name = results["metadatas"][0][0].get("riskName", "PromptInjectionAttack")
                    source_name = _HEURISTIC_SOURCE_NAMES.get("chromadb", "vectorSearch")
                    incidents.append({
                        "severity_weight": 1.0,
                        "frequency": 1,
                        "source": f"rebuff:{source_name}",
                        "risk_name": risk_name,
                    })
        except Exception as e:
            logger.debug(f"DPI-LS Risk Scanner: ChromaDB heuristic check failed: {e}")

    _set_cached_scan(cache_key, incidents)

    # --- Deduplicate by risk_name within this single scan call ---
    # If both LLM-Guard AND Rebuff fire on the same prompt for the same
    # attack type, collapse them into ONE incident (1 event, not 2).
    # Take the highest severity and concatenate sources for transparency.
    deduped: dict[str, dict] = {}
    for inc in incidents:
        rn = inc.get("risk_name", "Unknown")
        if rn not in deduped:
            entry = inc.copy()
            entry["_sources"] = [inc.get("source", "")]
            deduped[rn] = entry
        else:
            existing = deduped[rn]
            existing["severity_weight"] = max(
                float(existing.get("severity_weight", 0)),
                float(inc.get("severity_weight", 0))
            )
            src = inc.get("source", "")
            if src and src not in existing["_sources"]:
                existing["_sources"].append(src)
            existing["source"] = ", ".join(existing["_sources"])
    incidents = list(deduped.values())

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
