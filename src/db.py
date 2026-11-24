"""Safe, read-only access to the benchmark database."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "school.db"
SCHEMA_PATH = ROOT / "data" / "schema.sql"


class QueryTimeout(Exception):
    """Raised when a query runs longer than the allowed time."""


@dataclass
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)


def ensure_db(db_path: Path = DB_PATH) -> Path:
    """Build the database on first use so a fresh clone works without extra steps."""
    if not db_path.exists():
        import importlib.util

        spec = importlib.util.spec_from_file_location("seed", ROOT / "data" / "seed.py")
        seed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed)
        seed.build(db_path)
    return db_path


def connect_readonly(db_path: Path = DB_PATH) -> sqlite3.Connection:
    ensure_db(db_path)
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def run_query(conn: sqlite3.Connection, sql: str, timeout_s: float = 5.0,
              max_rows: int = 10_000) -> QueryResult:
    """Execute one SELECT statement with a time limit.

    Raises sqlite3.Error for invalid SQL and QueryTimeout when the limit is hit.
    The connection is read-only, so statements that modify data fail with an error.
    """
    deadline = time.perf_counter() + timeout_s

    def check_deadline() -> int:
        return 1 if time.perf_counter() > deadline else 0  # non-zero aborts the query

    conn.set_progress_handler(check_deadline, 10_000)
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(max_rows)
        columns = [d[0] for d in cur.description] if cur.description else []
        return QueryResult(columns=columns, rows=rows)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise QueryTimeout(f"query exceeded {timeout_s}s") from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)


def schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8").strip()
