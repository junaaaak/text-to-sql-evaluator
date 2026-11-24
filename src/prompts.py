"""The three prompt styles compared in the experiments.

zero_shot     schema + question
few_shot      schema + three worked examples + question
schema_hints  schema + sample rows, allowed values and data conventions + question
"""

from __future__ import annotations

from functools import lru_cache

from src.db import connect_readonly, run_query, schema_text

PROMPT_STYLES = ("zero_shot", "few_shot", "schema_hints")

SYSTEM = (
    "You are an expert SQLite developer. Write exactly one SQLite SELECT query that answers "
    "the user's question using the given database schema. Respond with the SQL query only, "
    "no explanation."
)

# Examples use the same schema but are not part of the benchmark.
FEW_SHOT_EXAMPLES = [
    ("How many students belong to the Physics department?",
     "SELECT COUNT(*) FROM students s JOIN departments d ON d.dept_id = s.dept_id "
     "WHERE d.name = 'Physics';"),
    ("List the titles of the courses taught by Dr. Raj Mehta in alphabetical order.",
     "SELECT title FROM courses WHERE instructor = 'Dr. Raj Mehta' ORDER BY title;"),
    ("What is the lowest score in each semester? Show the semester and the lowest score.",
     "SELECT c.semester, MIN(m.score) FROM marks m JOIN courses c ON c.course_id = m.course_id "
     "GROUP BY c.semester;"),
]

HINTS = """\
Notes about the data:
- Each row in marks is one student enrolled in one course; there is no separate enrollments table.
- marks.score is NULL when the exam has not been graded yet. AVG/MIN/MAX ignore NULLs.
- Dates are TEXT in 'YYYY-MM-DD' format.
- students.gender is 'M' or 'F'. courses.semester is 'Fall' or 'Spring'.
- students.year_of_study is 1-4. students.email can be NULL.
- Department names: {departments}.
- Return only the columns the question asks for, in the order it mentions them.
- Use ROUND(x, n) when the question asks for rounding."""


@lru_cache(maxsize=1)
def _sample_rows() -> str:
    conn = connect_readonly()
    parts = []
    for table in ("departments", "students", "courses", "marks"):
        res = run_query(conn, f"SELECT * FROM {table} LIMIT 3")
        lines = [" | ".join(res.columns)] + [" | ".join(map(str, r)) for r in res.rows]
        parts.append(f"{table}:\n" + "\n".join(lines))
    return "Sample rows:\n" + "\n\n".join(parts)


@lru_cache(maxsize=1)
def _department_names() -> str:
    rows = run_query(connect_readonly(), "SELECT name FROM departments ORDER BY dept_id").rows
    return ", ".join(f"'{r[0]}'" for r in rows)


def _user_message(question: str, extra: str = "") -> str:
    parts = [f"Database schema:\n{schema_text()}"]
    if extra:
        parts.append(extra)
    parts.append(f"Question: {question}\nSQL:")
    return "\n\n".join(parts)


def build_messages(style: str, question: str) -> list[dict]:
    if style == "zero_shot":
        return [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": _user_message(question)}]

    if style == "few_shot":
        messages = [{"role": "system", "content": SYSTEM}]
        for i, (q, sql) in enumerate(FEW_SHOT_EXAMPLES):
            # The schema is sent once, with the first example.
            content = _user_message(q) if i == 0 else f"Question: {q}\nSQL:"
            messages += [{"role": "user", "content": content},
                         {"role": "assistant", "content": sql}]
        messages.append({"role": "user", "content": f"Question: {question}\nSQL:"})
        return messages

    if style == "schema_hints":
        extra = _sample_rows() + "\n\n" + HINTS.format(departments=_department_names())
        return [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": _user_message(question, extra)}]

    raise ValueError(f"unknown prompt style {style!r}; choose from {PROMPT_STYLES}")
