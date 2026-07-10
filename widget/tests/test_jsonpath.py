from __future__ import annotations

import pytest

from ingestion.generic.jsonpath import resolve

PAYLOAD = {
    "a": {"b": {"c": 42}},
    "list": [{"x": 1}, {"x": 2}, {"x": 3}],
    "empty": None,
}


def test_dot_path():
    assert resolve("$.a.b.c", PAYLOAD) == 42


def test_optional_leading_dollar():
    assert resolve("a.b.c", PAYLOAD) == 42


def test_index():
    assert resolve("$.list[1].x", PAYLOAD) == 2


def test_wildcard_returns_list():
    assert resolve("$.list[*]", PAYLOAD) == [{"x": 1}, {"x": 2}, {"x": 3}]


def test_missing_key_returns_none():
    assert resolve("$.a.missing.deep", PAYLOAD) is None


def test_none_path_returns_none():
    assert resolve(None, PAYLOAD) is None


def test_root_path_returns_root():
    assert resolve("$", PAYLOAD) is PAYLOAD


def test_bad_syntax_raises():
    with pytest.raises(ValueError):
        resolve("$.a..b", PAYLOAD)


def test_index_out_of_range_returns_none():
    assert resolve("$.list[99].x", PAYLOAD) is None
