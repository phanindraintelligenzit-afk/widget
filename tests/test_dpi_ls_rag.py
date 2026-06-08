"""Tests for the general RAG patcher.

Covers:

* RAGPatcher wrapping ``retrieve`` / ``aretrieve`` /
  ``get_relevant_documents`` / ``ainvoke`` on a retriever-shaped object.
* Dispatcher auto-routing: any object with a ``.retriever`` attribute
  that's not matched by a more specific detector goes to RAGPatcher.
* LangChain-Retriever compatibility (the ``get_relevant_documents`` name).
* Collector-level ``record_retrieval`` bookkeeping.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from dpi_ls import SignalCollector
from dpi_ls.collector import _KIND_TOOL
from dpi_ls.frameworks import detect_and_install, detect_framework
from dpi_ls.frameworks.rag import RAGPatcher


# ---- direct patcher wrapping ---------------------------------------------

def test_rag_patcher_wraps_retrieve():
    class _Retriever:
        def retrieve(self, q: str):
            return [SimpleNamespace(node=SimpleNamespace(text="hit-" + q), score=0.8)]

    r = _Retriever()
    c = SignalCollector(agent_id="rag", agent_name="RAG")
    detect_and_install(r, c)
    nodes = r.retrieve("x")
    assert len(nodes) == 1
    # E — one successful execution.
    assert c.attempts == 1
    # RAG signals.
    assert c.retrievals == 1
    assert c.retrieved_docs_total == 1
    assert c.last_retrieval_top_score == pytest.approx(0.8)


def test_rag_patcher_wraps_aretrieve_async():
    class _Retriever:
        async def aretrieve(self, q: str):
            return [SimpleNamespace(node=SimpleNamespace(text="a"), score=0.5)]

    r = _Retriever()
    c = SignalCollector(agent_id="rag", agent_name="RAG")
    detect_and_install(r, c)
    asyncio.run(r.aretrieve("x"))
    assert c.retrievals == 1


def test_rag_patcher_wraps_get_relevant_documents_langchain_compat():
    """LangChain's BaseRetriever exposes ``get_relevant_documents``."""

    class _LangChainStyleRetriever:
        def get_relevant_documents(self, q: str):
            return [SimpleNamespace(page_content="doc-" + q)]

    r = _LangChainStyleRetriever()
    c = SignalCollector(agent_id="rag", agent_name="RAG")
    detect_and_install(r, c)
    docs = r.get_relevant_documents("y")
    assert len(docs) == 1
    assert c.retrievals == 1
    # page_content is the LangChain text attribute — captured.
    assert any("doc-y" in t for t, _ in zip(c._outputs, c._output_kinds) if _ == _KIND_TOOL)


# ---- dispatcher routing ---------------------------------------------------

def test_dispatcher_routes_to_rag_for_object_with_retriever_attr():
    """An object with a ``.retriever`` attribute auto-uses RAGPatcher.

    This is the path that catches LangChain ``RetrievalQA`` chains and
    any custom "chain-with-retriever" object that the framework
    detectors don't recognise.
    """

    class _Chain:
        # The class has no special module name, so no framework detector
        # matches — but the presence of a ``.retriever`` attribute
        # routes it to RAGPatcher.
        __module__ = "myapp.chains"

        def __init__(self):
            self.retriever = SimpleNamespace(retrieve=lambda q: [])

    chain = _Chain()
    assert detect_framework(chain).name == "rag"


def test_dispatcher_does_not_route_plain_object_to_rag():
    """A plain object with no ``.retriever`` attribute stays on UnknownPatcher."""

    class _Plain:
        __module__ = "myapp.plain"

        def invoke(self, x):
            return x

    obj = _Plain()
    assert detect_framework(obj).name == "unknown"


def test_dispatcher_does_not_route_class_object_to_rag():
    """A class (type) with a class-level ``retriever`` attribute doesn't auto-fire."""

    class _WithRetriever:
        retriever = "not an instance attr"

    # The class itself is a type — `isinstance(agent, type)` is True for
    # classes, so the ``hasattr + not isinstance(agent, type)`` guard
    # correctly excludes it. Users wouldn't typically monitor a class,
    # but the guard makes the dispatcher's intent explicit.
    assert detect_framework(_WithRetriever).name == "unknown"


# ---- nested retriever on a chain -----------------------------------------

def test_rag_patcher_wraps_nested_retriever():
    """An object whose ``.retriever`` is itself a retriever — wrap both."""

    class _InnerRetriever:
        def retrieve(self, q: str):
            return [SimpleNamespace(node=SimpleNamespace(text="inner"), score=0.9)]

    class _Outer:
        __module__ = "myapp.chain"
        def __init__(self):
            self.retriever = _InnerRetriever()

        def invoke(self, q: str):
            return self.retriever.retrieve(q)

    chain = _Outer()
    c = SignalCollector(agent_id="rag", agent_name="RAG")
    detect_and_install(chain, c)
    chain.invoke("x")
    # One retrieval from the inner retriever.
    assert c.retrievals == 1
    assert c.retrieved_docs_total == 1


# ---- collector-level record_retrieval ------------------------------------

def test_record_retrieval_increments_counters():
    c = SignalCollector(agent_id="x", agent_name="x")
    c.record_retrieval(docs_count=5, top_score=0.77)
    assert c.retrievals == 1
    assert c.retrieved_docs_total == 5
    assert c.last_retrieval_top_score == pytest.approx(0.77)
    assert c.attempts == 1
    assert c.successful == 1
    # record_retrieval does NOT increment total_outputs — the retrieval
    # is a tool call, not a generation.
    assert c.total_outputs == 0


def test_record_retrieval_with_failure():
    c = SignalCollector(agent_id="x", agent_name="x")
    c.record_retrieval(docs_count=0, ok=False)
    assert c.retrievals == 1
    assert c.attempts == 1
    assert c.failed == 1


def test_summary_includes_retrieval_signals():
    c = SignalCollector(agent_id="x", agent_name="x")
    c.record_retrieval(docs_count=3)
    s = c.summary()
    assert s["retrievals"] == 1
    assert s["retrieved_docs_total"] == 3
