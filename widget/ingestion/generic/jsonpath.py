"""Tiny JSONPath-lite resolver.

Supported syntax:
    $.a.b          dict access
    $.a[0]         list index
    $.a[*]         returns the whole list (caller iterates via _each)
    a.b            leading $ is optional

Anything fancier (filters, recursive descent, scripts) is intentionally
out of scope — keep mappings declarative and obvious.
"""
from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"\.([a-zA-Z_][a-zA-Z0-9_]*)|\[(\d+|\*)\]")


def resolve(path: str | None, root: Any) -> Any:
    if path is None:
        return None
    p = path.strip()
    if p.startswith("$"):
        p = p[1:]
    if not p:
        return root
    # Permit `a.b.c` (no leading `$`) by canonicalising to `.a.b.c` so the
    # token regex can pick it up.
    if not p.startswith((".", "[")):
        p = "." + p

    cur: Any = root
    pos = 0
    while pos < len(p):
        m = _TOKEN.match(p, pos)
        if not m:
            raise ValueError(f"Unparseable path '{path}' at position {pos}")
        key, idx = m.group(1), m.group(2)
        if cur is None:
            return None
        if key is not None:
            cur = cur.get(key) if isinstance(cur, dict) else None
        elif idx == "*":
            return list(cur) if isinstance(cur, list) else []
        else:
            try:
                cur = cur[int(idx)]
            except (IndexError, TypeError, KeyError):
                return None
        pos = m.end()
    return cur
