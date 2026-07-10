"""Tests for the LlamaIndex patcher.

These mirror the structure of ``test_dpi_ls_frameworks.py`` — fake
LlamaIndex-shaped objects (no real llama_index import needed) so the
tests run without the optional dependency installed.

Each test class explicitly sets ``__module__`` to a ``llama_index.*``
path so the dispatcher's module-name-based detector fires.

The tests exercise:

* detection by module name (``llama_index.core.query_engine`` etc.)
* wrapping of ``query`` / ``aquery`` / ``chat`` / ``achat``
* wrapping of ``retrieve`` / ``aretrieve`` as tool calls
* token extraction from ``response.metadata['usage']`` and ``response.raw['usage']``
* error path — exceptions during query increment R
* idempotency — ``install`` called twice doesn't double-wrap
* a query engine that has its own retriever (sub-call captured)
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from dpi_ls import SignalCollector
from dpi_ls.frameworks import detect_and_install, detect_framework
from dpi_ls.frameworks.base import already_patched
from dpi_ls.frameworks.llama_index import LlamaIndexPatcher


# ---- detection ------------------------------------------------------------

def test_detect_llama_index_query_engine():
    """A class whose module starts with ``llama_index`` is detected."""

    class _FakeQueryEngine:
        pass

    _FakeQueryEngine.__module__ = "llama_index.core.query_engine"
    assert detect_framework(_FakeQueryEngine()).name == "llama_index"


def test_detect_llama_index_retriever():
    class _FakeRetriever:
        pass

    _FakeRetriever.__module__ = "llama_index.core.retrievers"
    assert detect_framework(_FakeRetriever()).name == "llama_index"


# ---- query / aquery wrapping ---------------------------------------------

def test_query_method_wrapped_records_agent_run_and_output():
    """A single ``query()`` call drives P, E, and Q input."""

    class _Engine:
        def query(self, prompt: str) -> str:
            return f"answer to: {prompt}"

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(engine, c)
    out = engine.query("what is 2+2?")
    assert out == "answer to: what is 2+2?"
    # P — one agent run completed.
    assert c.agent_runs_completed == 1
    # E — one successful LLM call.
    assert c.attempts == 1
    assert c.successful == 1
    # Q input — the answer is captured as 'agent' kind.
    assert c.outputs_for_q() == ["answer to: what is 2+2?"]


def test_aquery_async_path():
    class _Engine:
        async def aquery(self, prompt: str) -> str:
            return f"async({prompt})"

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(engine, c)
    out = asyncio.run(engine.aquery("hi"))
    assert out == "async(hi)"
    assert c.agent_runs_completed == 1
    assert c.outputs_for_q() == ["async(hi)"]


def test_chat_method_wrapped():
    """BaseChatEngine.chat() is wrapped the same way as query()."""

    class _Engine:
        def chat(self, message: str) -> str:
            return f"chat: {message}"

    _Engine.__module__ = "llama_index.core.chat_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(engine, c)
    assert engine.chat("hello") == "chat: hello"
    assert c.agent_runs_completed == 1


# ---- retrieve / aretrieve wrapping ---------------------------------------

def test_retrieve_method_wrapped_as_tool_call():
    """A retrieval drives E and is captured as 'tool' (NOT sent to Q)."""

    class _Retriever:
        def retrieve(self, query: str):
            return [
                SimpleNamespace(node=SimpleNamespace(text="doc-1 about " + query), score=0.9),
                SimpleNamespace(node=SimpleNamespace(text="doc-2 about " + query), score=0.7),
            ]

    _Retriever.__module__ = "llama_index.core.retrievers"
    retriever = _Retriever()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(retriever, c)
    nodes = retriever.retrieve("python")
    assert len(nodes) == 2
    # E — a retrieval is one successful execution.
    assert c.attempts == 1
    assert c.successful == 1
    # RAG signals — counted and surfaced.
    assert c.retrievals == 1
    assert c.retrieved_docs_total == 2
    assert c.last_retrieval_top_score == pytest.approx(0.9)
    # The retrieved texts are tagged 'tool', not 'agent'. We confirm
    # this by inspecting the internal output kind list directly —
    # ``outputs_for_q`` falls back to all outputs when there are no
    # agent outputs, so we can't use it as a probe here.
    assert all(kind == "tool" for kind in c._output_kinds)


def test_aretrieve_async_wrapped():
    class _Retriever:
        async def aretrieve(self, query: str):
            return [
                SimpleNamespace(node=SimpleNamespace(text="async-doc"), score=0.5),
            ]

    _Retriever.__module__ = "llama_index.core.retrievers"
    r = _Retriever()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(r, c)
    asyncio.run(r.aretrieve("hi"))
    assert c.retrievals == 1
    assert c.retrieved_docs_total == 1


# ---- token extraction -----------------------------------------------------

def test_token_extraction_from_response_metadata():
    """Tokens come from response.metadata['usage'] (LlamaIndex's storage)."""

    class _Engine:
        def query(self, prompt: str):
            return SimpleNamespace(
                response="ok",
                metadata={"usage": {"prompt_tokens": 12, "completion_tokens": 8}},
            )

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(engine, c)
    engine.query("hi")
    assert c.tokens_in == 12
    assert c.tokens_out == 8
    # Cost is auto-estimated from the token counts.
    assert c.cloud_cost > 0


def test_token_extraction_from_response_raw_dict():
    """Tokens come from response.raw['usage'] (raw OpenAI shape)."""

    class _Engine:
        def query(self, prompt: str):
            return SimpleNamespace(
                response="ok",
                raw={"usage": {"prompt_tokens": 5, "completion_tokens": 7}},
            )

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(engine, c)
    engine.query("hi")
    assert c.tokens_in == 5
    assert c.tokens_out == 7


# ---- error path -----------------------------------------------------------

def test_query_with_exception_increments_R():
    class _Engine:
        def query(self, prompt: str):
            raise ConnectionError("upstream down")

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(engine, c)
    with pytest.raises(ConnectionError, match="upstream down"):
        engine.query("x")
    assert c.failed == 1
    assert len(c.incidents) == 1
    # ConnectionError is a network error → severity 1.0 (the policy in
    # the collector).
    assert c.incidents[0]["severity_weight"] == 1.0


# ---- idempotency ----------------------------------------------------------

def test_patches_are_idempotent():
    class _Engine:
        def query(self, prompt: str) -> str:
            return f"a: {prompt}"

        def retrieve(self, q: str):
            return []

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c1 = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    c2 = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    patched1 = detect_and_install(engine, c1)
    # Second install: wrappers are already patched, so the path list
    # is empty — but the collector is swapped via the shared
    # ``_dpi_ls_collector_ref`` so subsequent calls write to c2.
    patched2 = detect_and_install(engine, c2)
    assert patched1  # first install patched something
    assert patched2 == []  # second install: nothing new to patch
    # Calling query now writes to the second collector only.
    engine.query("z")
    assert c2.agent_runs_completed == 1
    # First collector is untouched.
    assert c1.agent_runs_completed == 0


# ---- combined: query engine that calls its own retriever -------------------

def test_query_engine_with_retriever_captures_both_calls():
    """A RetrieverQueryEngine's inner retrieve() is observed too."""

    class _InnerRetriever:
        def retrieve(self, q: str):
            return [
                SimpleNamespace(node=SimpleNamespace(text="doc-" + q), score=0.8),
                SimpleNamespace(node=SimpleNamespace(text="also-" + q), score=0.6),
            ]

    _InnerRetriever.__module__ = "llama_index.core.retrievers"

    class _Engine:
        def __init__(self):
            self.retriever = _InnerRetriever()

        def query(self, prompt: str):
            # Real query engines retrieve first, then synthesise. We
            # mirror that here.
            self.retriever.retrieve(prompt)
            return SimpleNamespace(
                response="synthesised",
                metadata={"usage": {"prompt_tokens": 4, "completion_tokens": 9}},
            )

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    detect_and_install(engine, c)
    engine.query("rag")
    # P — one query = one agent run.
    assert c.agent_runs_completed == 1
    # E — the query's LLM call AND the inner retrieval are both counted.
    assert c.attempts == 2
    assert c.successful == 2
    # RAG signals.
    assert c.retrievals == 1
    assert c.retrieved_docs_total == 2
    # C — tokens from the LLM call (the retrieval has no tokens).
    assert c.tokens_in == 4
    assert c.tokens_out == 9
    # Q input — only the synthesised answer, not the retrieved docs.
    assert c.outputs_for_q() == ["synthesised"]


# ---- direct patcher invocation -------------------------------------------

def test_llama_index_patcher_direct_install():
    """Calling install() twice doesn't double-wrap."""

    class _Engine:
        def query(self, prompt: str) -> str:
            return "x"

    _Engine.__module__ = "llama_index.core.query_engine"
    engine = _Engine()
    c = SignalCollector(agent_id="li", agent_name="LlamaIndex")
    p = LlamaIndexPatcher()
    paths1 = p.install(engine, c)
    paths2 = p.install(engine, c)
    # First install patches something; second is a no-op (wrappers
    # already marked).
    assert paths1
    assert paths2 == []
    assert any("query" in p_ for p_ in paths1)
