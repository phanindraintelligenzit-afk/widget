from __future__ import annotations

import pytest

from contract import AgentObservation
from ingestion import Adapter, clear, get, list_adapters, register


class _DummyAdapter(Adapter):
    name = "dummy"

    def to_observations(self, payload):
        return []


def setup_function(_):
    clear()


def test_register_and_get():
    a = _DummyAdapter()
    register(a)
    assert get("dummy") is a
    assert list_adapters() == ["dummy"]


def test_register_rejects_blank_name():
    a = _DummyAdapter()
    a.name = ""
    with pytest.raises(ValueError):
        register(a)


def test_duplicate_register_requires_replace():
    register(_DummyAdapter())
    with pytest.raises(ValueError):
        register(_DummyAdapter())
    register(_DummyAdapter(), replace=True)


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        get("nope")
