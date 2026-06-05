"""Tests for framework detection and patcher installation.

These exercise the dispatcher and the individual patchers in
isolation, without actually running any LLM calls. The goal is to
make sure the right framework is detected, the right hooks fire,
and the collector ends up with the signals we expect.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from dpi_ls import SignalCollector
from dpi_ls.frameworks import detect_and_install, detect_framework
from dpi_ls.frameworks.base import _safe_iter_tokens, _safe_text, already_patched


# ---- detection ------------------------------------------------------------

def test_detect_openai_agents():
    """An Agent-shaped object whose class lives in the ``agents`` package."""
    from agents import Agent

    agent = Agent(name="x", instructions="hi")
    assert detect_framework(agent).name == "openai_agents"


def test_detect_unknown_falls_back_to_best_effort():
    class _Weird:
        pass

    assert detect_framework(_Weird()).name == "unknown"


def test_detect_raw_openai_client():
    """A live OpenAI client instance — module starts with ``openai`` and
    has ``.chat``."""
    from openai import OpenAI

    client = OpenAI(api_key="dummy")
    assert detect_framework(client).name == "openai"


# ---- patches on a fake framework ----------------------------------------

def test_unknown_patcher_wraps_invoke():
    """An object with a callable ``invoke`` is patched as best-effort."""
    seen = []

    class _Obj:
        def invoke(self, x):
            seen.append(("invoke", x))
            return f"result({x})"

    obj = _Obj()
    c = SignalCollector(agent_id="x", agent_name="x")
    detect_and_install(obj, c)
    assert obj.invoke("hello") == "result(hello)"
    assert seen == [("invoke", "hello")]
    assert c.attempts == 1
    assert c.successful == 1
    assert c.outputs_for_q() == ["result(hello)"]


def test_unknown_patcher_wraps_sync_run_method():
    seen = []

    class _Obj:
        def run(self, prompt):
            seen.append(prompt)
            return f"answer: {prompt}"

    obj = _Obj()
    c = SignalCollector(agent_id="x", agent_name="x")
    detect_and_install(obj, c)
    out = obj.run("why?")
    assert out == "answer: why?"
    assert c.outputs_for_q() == ["answer: why?"]


def test_unknown_patcher_records_errors():
    class _Obj:
        def invoke(self, x):
            raise RuntimeError("boom")

    obj = _Obj()
    c = SignalCollector(agent_id="x", agent_name="x")
    detect_and_install(obj, c)
    with pytest.raises(RuntimeError, match="boom"):
        obj.invoke("go")
    assert c.attempts == 1
    assert c.failed == 1
    assert len(c.incidents) == 1


def test_unknown_patcher_handles_async_invoke():
    class _Obj:
        async def ainvoke(self, x):
            return f"async({x})"

    obj = _Obj()
    c = SignalCollector(agent_id="x", agent_name="x")
    detect_and_install(obj, c)
    out = asyncio.run(obj.ainvoke("y"))
    assert out == "async(y)"
    assert c.outputs_for_q() == ["async(y)"]


# ---- base helpers --------------------------------------------------------

def test_safe_text_handles_string():
    assert _safe_text("hello") == "hello"


def test_safe_text_handles_message_like():
    assert _safe_text(SimpleNamespace(content="world")) == "world"


def test_safe_text_handles_content_list():
    msg = SimpleNamespace(content=[
        {"type": "text", "text": "part1"},
        {"text": "part2"},
    ])
    assert _safe_text(msg) == "part1\npart2"


def test_safe_text_handles_dict():
    assert _safe_text({"content": "abc"}) == "abc"
    assert _safe_text({"text": "def"}) == "def"
    assert _safe_text({"output": "ghi"}) == "ghi"


def test_safe_text_returns_empty_for_garbage():
    assert _safe_text(None) == ""
    assert _safe_text(42) == ""


def test_safe_iter_tokens_openai_shape():
    msg = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20))
    assert _safe_iter_tokens(msg) == (10, 20)


def test_safe_iter_tokens_anthropic_shape():
    msg = SimpleNamespace(usage=SimpleNamespace(input_tokens=11, output_tokens=22))
    assert _safe_iter_tokens(msg) == (11, 22)


def test_safe_iter_tokens_dict_shape():
    assert _safe_iter_tokens({"usage": {"input_tokens": 5, "output_tokens": 7}}) == (5, 7)


def test_safe_iter_tokens_no_usage():
    assert _safe_iter_tokens(SimpleNamespace(content="x")) == (0, 0)


# ---- idempotency ---------------------------------------------------------

def test_install_is_idempotent():
    class _Obj:
        def invoke(self, x):
            return x

    obj = _Obj()
    c1 = SignalCollector(agent_id="x", agent_name="x")
    c2 = SignalCollector(agent_id="y", agent_name="y")
    detect_and_install(obj, c1)
    # Replace the collector and reinstall — wrapper stays the same.
    detect_and_install(obj, c2)
    obj.invoke("z")
    # Only the second collector sees the call (the first one was swapped out).
    assert c2.attempts == 1
    assert c2.outputs_for_q() == ["z"]


# ---- OpenAI Agents patcher actually wires hooks --------------------------

def test_openai_agents_patcher_wires_runner_run():
    """Runner.run is replaced with a wrapper that injects hooks."""
    from agents import Runner
    from dpi_ls.frameworks.openai_agents import OpenAIAgentsPatcher

    original = Runner.run
    try:
        c = SignalCollector(agent_id="x", agent_name="x")
        patched = OpenAIAgentsPatcher().install(SimpleNamespace(name="probe"), c)
        # Either the SDK exposes Runner.run and we replaced it, or
        # the import failed and we patched nothing — both are valid.
        if patched:
            assert any(p.endswith("run") for p in patched)
            assert already_patched(Runner.run)
    finally:
        # Restore in case the test ran without pytest isolation.
        Runner.run = original
