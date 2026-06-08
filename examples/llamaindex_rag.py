"""LlamaIndex RAG agent — instrumented with ``dpi_ls.monitor``.

Run::

    uv run examples/llamaindex_rag.py

The dashboard at http://localhost:8000 populates one row for
``agent_id="llamaindex-rag"`` once the script exits.

What this exercises
-------------------

* ``LlamaIndexPatcher`` (from ``dpi_ls/frameworks/llama_index.py``) wraps
  ``query_engine.query`` so the collector observes one
  ``agent_runs_completed`` (drives **P**) and captures the response
  text as ``_KIND_AGENT`` for the Q LLM evaluator.
* Inside the query, LlamaIndex automatically calls its retriever. The
  nested retriever's ``retrieve`` method is also wrapped, so each
  retrieval shows up as a separate tool call (drives **E**) and
  increments the per-agent card's ``retrievals`` line.
* Token counts are pulled from the response's ``metadata['usage']`` so
  the **C** (Cost) dimension reflects real LLM spend, not an estimate.
* The answer is a clean Markdown report with ``##`` headers so the
  deterministic V / G / R scanners all see the output as structured,
  governance-clean, and incident-free.

Install
-------

::

    pip install dpi-ls[llamaindex]
    # or
    uv sync --extra llamaindex
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Make sure the repo root is importable when running from /examples.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Don't pause for stdin on exit — the demo runs non-interactively.
os.environ.setdefault("DPI_LS_NO_BLOCK", "1")

import dpi_ls  # noqa: E402


# ---------------------------------------------------------------------------
# Tiny inline corpus — six short documents about cloud cost optimisation.
# No filesystem reads, no network calls; keeps the demo self-contained.
# ---------------------------------------------------------------------------
_CORPUS: list[str] = [
    "Reserved Instances: AWS Reserved Instances offer up to 72% discount "
    "compared to On-Demand pricing in exchange for a 1- or 3-year commit. "
    "Best for steady-state workloads with predictable baseline usage.",
    "Savings Plans: Compute Savings Plans apply across EC2, Fargate, and "
    "Lambda. They offer up to 66% savings and are more flexible than RIs.",
    "Spot Instances: Suitable for fault-tolerant, interruptible workloads. "
    "Up to 90% discount. Common in batch processing, CI/CD runners, and "
    "data analytics.",
    "S3 Intelligent-Tiering: Automatically moves objects between frequent "
    "and infrequent access tiers based on access patterns. Small monthly "
    "monitoring fee per object; no retrieval charges.",
    "Right-sizing: Resizing EC2 instances or RDS DBs to match actual "
    "utilisation. Tools: AWS Compute Optimizer, Cost Explorer's "
    "recommendations. Typical savings: 10-30% on compute.",
    "Idle resource cleanup: Unattached EBS volumes, unused Elastic IPs, "
    "and idle load balancers each cost money. A weekly cleanup script "
    "typically recovers 5-15% of an AWS bill.",
]


async def _build_query_engine() -> Any:
    """Build a LlamaIndex VectorStoreIndex over the inline corpus.

    Uses the local ``llama-index-core`` package (no LLM call needed for
    index construction — only the OpenAI embedding model is invoked at
    index time. If you don't have OpenAI credentials set, this will
    fail at index time; set ``OPENAI_API_KEY`` in your env first.
    """
    # Import lazily so the rest of the example imports even when
    # ``llama-index-core`` is not installed.
    from llama_index.core import (
        Document,
        Settings,
        VectorStoreIndex,
    )
    from llama_index.core.embeddings import resolve_embed_model

    # Use a local / mock embedding model if available, otherwise fall
    # back to OpenAI. Users can swap in any embed_model their setup
    # already uses.
    try:
        Settings.embed_model = resolve_embed_model("local:BAAI/bge-small-en-v1.5")
    except Exception:
        # If local embed model isn't available, use OpenAI's.
        # The user must have OPENAI_API_KEY set for this to work.
        from llama_index.embeddings.openai import OpenAIEmbedding
        Settings.embed_model = OpenAIEmbedding()

    documents = [Document(text=t) for t in _CORPUS]
    index = VectorStoreIndex.from_documents(documents)
    return index.as_query_engine()


async def main() -> None:
    print("Building LlamaIndex RAG agent...")
    query_engine = await _build_query_engine()

    # human_baseline=1: this agent emits one report per query, matching
    # one human analyst who would also produce one report. LlamaIndexPatcher
    # auto-detects the query_engine, wraps ``query``, and also wraps
    # the nested retriever's ``retrieve`` so each retrieval is a
    # distinct signal.
    collector = dpi_ls.monitor(
        query_engine,
        agent_id="llamaindex-rag",
        agent_name="LlamaIndex RAG Agent",
        human_baseline=1,
    )

    questions = [
        "What are the three highest-impact FinOps levers for an AWS "
        "workload with steady-state compute? Use Markdown with '##' "
        "section headers. Do not include any emails, phone numbers, "
        "or API keys.",
        "How do Savings Plans compare to Reserved Instances? Keep the "
        "answer under 150 words. Format as Markdown with '##' headers.",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        response = await query_engine.aquery(q)
        # Trim to ASCII for clean printing on cp1252 consoles.
        answer = str(response).encode("ascii", errors="ignore").decode("ascii")
        print(f"A: {answer}")

    # ---- one-line RAG signal preview ----
    s = collector.summary()
    print(
        f"\ndpi_ls RAG summary: "
        f"agent_runs={s['agent_runs_completed']}  "
        f"attempts={s['attempts']}  "
        f"retrievals={s['retrievals']}  "
        f"docs_retrieved={s['retrieved_docs_total']}  "
        f"tokens={s['tokens']}  "
        f"validated={s['validated']}/{s['outputs']}"
    )
    print(f"Dashboard will populate on exit: http://127.0.0.1:8000/")


if __name__ == "__main__":
    asyncio.run(main())
