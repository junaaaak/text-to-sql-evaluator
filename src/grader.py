"""Execution-accuracy grading: run predicted and gold SQL, compare their results.

Comparison rules
- Rows are compared as a multiset (duplicates count) unless the gold query has a
  top-level ORDER BY, in which case row order must match too.
- Numbers are compared after rounding to 2 decimals (so 3 == 3.0 and 66.666 == 66.67).
- Column names are ignored. Column order is also ignored: the prediction matches if
  some reordering of its columns reproduces the gold result.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from itertools import permutations

import sqlglot
from sqlglot import exp

from src.db import QueryTimeout, run_query

# Statuses. Everything except CORRECT and WRONG_RESULT counts as "failed to run".
CORRECT = "correct"
WRONG_RESULT = "wrong_result"
SYNTAX_ERROR = "syntax_error"
SCHEMA_ERROR = "schema_error"
EXECUTION_ERROR = "execution_error"
TIMEOUT = "timeout"
NO_SQL = "no_sql"
FAILED_TO_RUN = {SYNTAX_ERROR, SCHEMA_ERROR, EXECUTION_ERROR, TIMEOUT, NO_SQL}

MAX_PERMUTED_COLUMNS = 6


@dataclass
class Grade:
    status: str
    error: str | None = None
    pred_row_count: int | None = None

    @property
    def correct(self) -> bool:
        return self.status == CORRECT

    @property
    def failed_to_run(self) -> bool:
        return self.status in FAILED_TO_RUN


def normalize_value(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return round(float(value), 2) + 0.0  # + 0.0 turns -0.0 into 0.0
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def normalize_rows(rows: list[tuple]) -> list[tuple]:
    return [tuple(normalize_value(v) for v in row) for row in rows]


def has_top_level_order_by(sql: str) -> bool:
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:  # noqa: BLE001 - fall back to a rough check
        return bool(re.search(r"\border\s+by\b[^)]*$", sql, re.IGNORECASE | re.DOTALL))
    if isinstance(tree, exp.Subquery):
        tree = tree.this
    return tree is not None and tree.args.get("order") is not None


def _sortable(row: tuple) -> tuple:
    # None and mixed types cannot be compared directly; sort by (type name, value).
    return tuple((type(v).__name__, v) if v is not None else ("", "") for v in row)


def results_match(gold: list[tuple], pred: list[tuple], ordered: bool) -> bool:
    gold, pred = normalize_rows(gold), normalize_rows(pred)
    if len(gold) != len(pred):
        return False
    if not gold:
        return True
    n_cols = len(gold[0])
    if any(len(r) != n_cols for r in pred):
        return False

    column_orders = (permutations(range(n_cols)) if n_cols <= MAX_PERMUTED_COLUMNS
                     else [tuple(range(n_cols))])
    gold_counter = None if ordered else Counter(gold)
    for order in column_orders:
        candidate = [tuple(row[i] for i in order) for row in pred]
        if ordered:
            if candidate == gold:
                return True
        elif Counter(candidate) == gold_counter:
            return True
    return False


def classify_error(exc: Exception) -> str:
    if isinstance(exc, QueryTimeout):
        return TIMEOUT
    msg = str(exc).lower()
    if "no such table" in msg or "no such column" in msg or "ambiguous column" in msg \
            or "no such function" in msg:
        return SCHEMA_ERROR
    if "syntax error" in msg or "incomplete input" in msg or "unrecognized token" in msg:
        return SYNTAX_ERROR
    return EXECUTION_ERROR


def grade(conn: sqlite3.Connection, gold_sql: str, pred_sql: str | None,
          timeout_s: float = 5.0) -> Grade:
    if not pred_sql or not pred_sql.strip():
        return Grade(NO_SQL, error="model returned no SQL")

    gold = run_query(conn, gold_sql, timeout_s=timeout_s)  # gold queries are validated
    try:
        pred = run_query(conn, pred_sql, timeout_s=timeout_s)
    except (sqlite3.Error, QueryTimeout, ValueError) as exc:
        return Grade(classify_error(exc), error=str(exc))

    ordered = has_top_level_order_by(gold_sql)
    status = CORRECT if results_match(gold.rows, pred.rows, ordered) else WRONG_RESULT
    return Grade(status, pred_row_count=len(pred.rows))
