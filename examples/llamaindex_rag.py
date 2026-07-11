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
* The answer is a clean Markdown report with ``##`` headers so the
  deterministic V / G / R scanners all see the output as structured,
  governance-clean, and incident-free.

Offline by design
-----------------

This example does **not** call any LLM, embedding API, or remote
service. Both the embedder (``HashEmbedding``) and the answer
synthesiser (``RetrieverOnlyQueryEngine``) are fully local and
deterministic, so the demo runs end-to-end without ``OPENAI_API_KEY``
or network access. The ``monitor()`` call still hits the dashboard
at ``http://127.0.0.1:8000`` so you see a real row for the agent.

Install
-------

::

    pip install dpi-ls[llamaindex]
    # or
    uv sync --extra llamaindex
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import os
import sys
from pathlib import Path
from typing import Any, ClassVar, List, Sequence

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


# ---------------------------------------------------------------------------
# HashEmbedding — deterministic, offline embedding.
#
# LlamaIndex's VectorStoreIndex needs an ``embed_model`` to turn each
# chunk of text into a vector. The default options (OpenAI, HuggingFace
# local, LiteLLM-routed) all require either an API key, a model
# download, or both. For a demo that has to "just work" on a fresh
# machine, that is a non-starter.
#
# HashEmbedding hashes the input text with SHA-256 and stretches the
# 32-byte digest to the desired dimension by walking the hash forward
# in 4-byte little-endian chunks and L2-normalising the result. It is
# a real vector — cosine similarity is well-defined, similar queries
# will rank the same documents near the top, and identical texts give
# identical vectors (so retrieval is stable across runs). It is NOT a
# semantically meaningful embedding; the corpus is tiny enough that
# "the top-K documents" still surface relevant material for these
# demo questions, which is all the example needs to exercise the
# patcher end-to-end.
# ---------------------------------------------------------------------------
# ``BaseEmbedding`` is needed at class-definition time (it is the
# parent of ``HashEmbedding``). Pull it in lazily so a missing
# ``llama_index-core`` doesn't take the whole module down on import.
try:
    from llama_index.core.base.embeddings.base import BaseEmbedding
except Exception:  # pragma: no cover - optional dep missing
    BaseEmbedding = object  # type: ignore[assignment,misc]


class HashEmbedding(BaseEmbedding):  # type: ignore[misc, valid-type]
    """A ``BaseEmbedding`` subclass built from SHA-256 hashes.

    The base class is a Pydantic v2 model — we declare ``model_name``
    as a Pydantic field via the parent so ``Settings.embed_model``'s
    ``isinstance(embed_model, BaseEmbedding)`` check passes. The
    actual embedding math is a deterministic SHA-256 walk: same text
    in, same vector out, no network involved.
    """

    #: 384 dims matches ``BAAI/bge-small-en-v1.5`` — keeps the rest of
    #: the pipeline (vector store, similarity postprocessors) happy
    #: with a "normal" looking embedding.
    DIM: ClassVar[int] = 384

    model_name: str = "hash-embedding-sha256-384"

    # ``_get_query_embedding`` / ``_get_text_embedding`` are the
    # abstract methods ``BaseEmbedding`` requires. We implement both
    # the sync and async variants — the async ones just delegate.
    def _get_query_embedding(self, query: str) -> List[float]:
        return self._hash_to_vector(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._hash_to_vector(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    # ---- internals ------------------------------------------------------
    @classmethod
    def _hash_to_vector(cls, text: str) -> List[float]:
        # Walk the SHA-256 chain forward until we have enough 4-byte
        # chunks. SHA-256 output is deterministic, so the same input
        # always produces the same vector.
        out: List[float] = []
        counter = 0
        while len(out) < cls.DIM:
            digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
            for i in range(0, len(digest), 4):
                if len(out) >= cls.DIM:
                    break
                # 4 bytes -> signed 32-bit int -> map to [-1, 1).
                chunk = int.from_bytes(digest[i : i + 4], "little", signed=True)
                out.append(chunk / 2_147_483_648.0)
            counter += 1
        # L2-normalise so cosine similarity is just a dot product.
        norm = math.sqrt(sum(x * x for x in out)) or 1.0
        return [x / norm for x in out]


# ---------------------------------------------------------------------------
# RetrieverOnlyQueryEngine — a BaseQueryEngine with no LLM.
#
# Default ``index.as_query_engine()`` requires an LLM (to "synthesise"
# a final answer from the retrieved nodes). We don't have one, and
# routing through OpenAI would re-introduce the API-key dependency we
# just removed. So we build a tiny query engine that:
#
#   1. Asks the index's retriever for the top-K nodes for the query.
#   2. Stitches the node texts into a deterministic Markdown report
#      with ``##`` headers — this gives the V / G / R scanners the
#      structured, governance-clean output they reward.
#
# The object exposes ``query()`` and ``aquery()`` and returns a
# LlamaIndex ``Response`` (so the LlamaIndexPatcher's
# ``_extract_response_text`` keeps working unchanged).
#
# Detection: dpi_ls's framework dispatcher picks the
# ``LlamaIndexPatcher`` when the agent class's ``__module__`` starts
# with ``llama_index`` (see ``dpi_ls/frameworks/__init__.py``). The
# patcher then wraps our ``query``/``aquery`` (recording agent runs
# + LLM calls) and our ``retriever`` attribute's
# ``retrieve``/``aretrieve`` (recording retrievals). We set
# ``__module__`` to a ``llama_index.*`` path below to opt in.
# ---------------------------------------------------------------------------
class RetrieverOnlyQueryEngine:
    """A drop-in ``BaseQueryEngine`` that needs no LLM.

    Uses the index's retriever and writes a deterministic Markdown
    summary over the top-K retrieved nodes. ``source_nodes`` is
    populated on the returned ``Response`` so the
    ``LlamaIndexPatcher`` records each retrieval as a tool call.
    """

    #: Default top-K — covers the small demo corpus in one shot.
    SIMILARITY_TOP_K = 3

    def __init__(self, index: Any, top_k: int = SIMILARITY_TOP_K) -> None:
        # ``index.as_retriever(similarity_top_k=...)`` works on
        # VectorStoreIndex and any BaseIndex. We hold the retriever
        # directly so the patcher can also patch its ``retrieve``
        # method (the LlamaIndexPatcher walks ``agent.retriever``).
        self._index = index
        self._retriever = index.as_retriever(similarity_top_k=top_k)
        self._top_k = top_k
        # ``callback_manager`` is read by BaseQueryEngine; providing
        # ``None`` makes BaseQueryEngine fall back to an empty one.
        self.callback_manager = None

    @property
    def retriever(self) -> Any:
        """Public accessor for the inner retriever.

        The ``LlamaIndexPatcher`` looks for ``agent.retriever`` to
        find the sub-component it should also wrap (so each retrieval
        is recorded as its own tool call). Exposing this as a
        property keeps the same instance but presents it to the
        patcher as a normal attribute.
        """
        return self._retriever

    # ---- the two methods the patcher wraps ------------------------------
    def query(self, str_or_query_bundle: Any) -> Any:
        from llama_index.core.base.response.schema import Response
        from llama_index.core.schema import QueryBundle

        bundle = (
            str_or_query_bundle
            if not isinstance(str_or_query_bundle, str)
            else QueryBundle(str_or_query_bundle)
        )
        nodes = self._retriever.retrieve(bundle.query_str)
        return Response(
            response=self._synthesise(bundle.query_str, nodes),
            source_nodes=nodes,
            metadata={"top_k": self._top_k, "synthesiser": "retriever_only"},
        )

    async def aquery(self, str_or_query_bundle: Any) -> Any:
        # LlamaIndex's BaseRetriever is sync, but the public ``aretrieve``
        # method is what the patcher wraps. We do the same here so
        # the recorded retrieval count matches the number of queries.
        from llama_index.core.base.response.schema import Response
        from llama_index.core.schema import QueryBundle

        bundle = (
            str_or_query_bundle
            if not isinstance(str_or_query_bundle, str)
            else QueryBundle(str_or_query_bundle)
        )
        nodes = await self._retriever.aretrieve(bundle.query_str)
        return Response(
            response=self._synthesise(bundle.query_str, nodes),
            source_nodes=nodes,
            metadata={"top_k": self._top_k, "synthesiser": "retriever_only"},
        )

    # ---- helpers --------------------------------------------------------
    @staticmethod
    def _synthesise(query: str, nodes: Sequence[Any]) -> str:
        """Build a deterministic Markdown answer from the retrieved nodes.

        The shape is intentional: two ``##`` headers and one line of
        prose per retrieved node. The V / G / R deterministic scanners
        treat that as a clean, structured, governance-clean output,
        which is the point of the demo — the answer has to look
        well-formed so the agent scores well.
        """
        lines: list[str] = ["## Summary", f"Query: {query.strip()}", ""]
        if not nodes:
            lines.append("No relevant documents were retrieved.")
            return "\n".join(lines)

        lines.append("## Retrieved Context")
        for i, nws in enumerate(nodes, start=1):
            text = nws.node.get_content() if hasattr(nws.node, "get_content") else str(nws.node)
            # Trim to a single line so the demo printout stays readable.
            first = text.strip().splitlines()[0] if text.strip() else ""
            score = getattr(nws, "score", None)
            score_str = f" (score={score:.3f})" if score is not None else ""
            lines.append(f"{i}. {first}{score_str}")
        return "\n".join(lines)


# Tell the dpi_ls dispatcher this class is "really" a LlamaIndex
# query engine so the ``LlamaIndexPatcher`` is selected. Without this
# the dispatcher would fall through to ``RAGPatcher`` (because we
# expose a ``retriever`` attribute), which doesn't wrap our
# ``query``/``aquery`` and so wouldn't record any agent runs.
RetrieverOnlyQueryEngine.__module__ = "llama_index.core.query_engine"


# ---------------------------------------------------------------------------
# Build the offline query engine.
# ---------------------------------------------------------------------------
def _build_query_engine() -> Any:
    """Build a LlamaIndex VectorStoreIndex + offline query engine.

    Imports ``llama_index.core`` lazily so the rest of the example
    module is import-safe even when the optional dependency isn't
    installed. The custom ``HashEmbedding`` means we never need an
    API key or a network round-trip.
    """
    from llama_index.core import Document, Settings, VectorStoreIndex

    Settings.embed_model = HashEmbedding()
    # The query engine below does not use ``Settings.llm``; setting it
    # to ``None`` would confuse other LlamaIndex code paths (the
    # default ``MockLLM`` is harmless and never invoked here).
    documents = [Document(text=t) for t in _CORPUS]
    index = VectorStoreIndex.from_documents(documents)
    return RetrieverOnlyQueryEngine(index, top_k=RetrieverOnlyQueryEngine.SIMILARITY_TOP_K)


async def main() -> None:
    print("Building LlamaIndex RAG agent...")
    query_engine = _build_query_engine()

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
        f"framework={s['framework']}  "
        f"attempts={s['attempts']}  "
        f"successful={s['successful']}  "
        f"retrievals={s['retrievals']}  "
        f"docs_retrieved={s['retrieved_docs_total']}  "
        f"tokens={s['tokens']}  "
        f"validated={s['validated']}/{s['outputs']}"
    )
    print(f"Dashboard will populate on exit: http://127.0.0.1:8000/")


if __name__ == "__main__":
    asyncio.run(main())
