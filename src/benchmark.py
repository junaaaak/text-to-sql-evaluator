"""Load and validate the benchmark question set."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.db import ROOT, connect_readonly, run_query

QUESTIONS_PATH = ROOT / "data" / "questions.jsonl"
DIFFICULTIES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class Question:
    id: str
    difficulty: str
    type: str
    question: str
    gold_sql: str


def load_questions(path: Path = QUESTIONS_PATH) -> list[Question]:
    questions = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            questions.append(Question(**json.loads(line)))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"{path.name}:{line_no}: {exc}") from exc
    return questions


def validate(questions: list[Question], verbose: bool = False) -> list[str]:
    """Return a list of problems; an empty list means the benchmark is valid."""
    problems = []
    ids = Counter(q.id for q in questions)
    problems += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    problems += [f"{q.id}: unknown difficulty {q.difficulty!r}"
                 for q in questions if q.difficulty not in DIFFICULTIES]

    conn = connect_readonly()
    for q in questions:
        try:
            result = run_query(conn, q.gold_sql)
        except Exception as exc:  # noqa: BLE001 - report every failure
            problems.append(f"{q.id}: gold SQL failed: {exc}")
            continue
        if not result.rows:
            problems.append(f"{q.id}: gold SQL returned no rows")
        elif all(v is None for row in result.rows for v in row):
            problems.append(f"{q.id}: gold SQL returned only NULLs")
        if verbose:
            preview = result.rows[:4]
            more = f" ... (+{len(result.rows) - 4})" if len(result.rows) > 4 else ""
            print(f"{q.id} [{q.difficulty:6s} {q.type:22s}] {len(result.rows):3d} rows  {preview}{more}")
    return problems


if __name__ == "__main__":
    import sys

    qs = load_questions()
    counts = Counter(q.difficulty for q in qs)
    print(f"{len(qs)} questions: " + ", ".join(f"{d}={counts[d]}" for d in DIFFICULTIES))
    issues = validate(qs, verbose="-v" in sys.argv)
    for issue in issues:
        print("PROBLEM:", issue)
    print("Benchmark OK" if not issues else f"{len(issues)} problem(s)")
    sys.exit(1 if issues else 0)
