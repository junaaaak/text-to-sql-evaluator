"""Pull a single SQL statement out of a model's free-text reply."""

from __future__ import annotations

import re

_FENCE = re.compile(r"```[ \t]*(?:sql|sqlite)?[ \t]*\n?(.*?)```", re.IGNORECASE | re.DOTALL)
_SQL_START = re.compile(r"\b(WITH|SELECT)\b", re.IGNORECASE)


def _first_statement(sql: str) -> str:
    """Cut at the first semicolon that is not inside a string literal."""
    in_single = in_double = False
    for i, ch in enumerate(sql):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double:
            return sql[:i]
    return sql


def extract_sql(text: str | None) -> str:
    """Return the first SQL statement in text, or '' if none is found."""
    if not text:
        return ""
    fenced = [block for block in _FENCE.findall(text) if _SQL_START.search(block)]
    if fenced:
        candidate = fenced[0]
    else:
        match = _SQL_START.search(text)
        if not match:
            return ""
        candidate = text[match.start():]
        has_semicolon = _first_statement(candidate) != candidate
        if not has_semicolon:
            # Without a semicolon, assume prose starts after the first blank line.
            candidate = re.split(r"\n\s*\n", candidate, maxsplit=1)[0]
    return _first_statement(candidate).strip()
