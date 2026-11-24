"""Build data/school.db from schema.sql with deterministic, seeded data.

Run:  python data/seed.py
The same seed always produces the same database, so benchmark results are reproducible.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "school.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"
SEED = 42

DEPARTMENTS = [
    (1, "Computer Science", "Turing Hall"),
    (2, "Mathematics", "Euler Building"),
    (3, "Physics", "Curie Centre"),
    (4, "Economics", "Smith House"),
    (5, "History", "Gibbon Hall"),
]

# (code, title, dept_id, credits, instructor, semester)
COURSES = [
    ("CS101", "Introduction to Programming", 1, 4, "Dr. Ada Shaw", "Fall"),
    ("CS201", "Data Structures", 1, 4, "Dr. Ada Shaw", "Spring"),
    ("CS301", "Databases", 1, 3, "Dr. Ken Ito", "Fall"),
    ("MA101", "Calculus I", 2, 4, "Dr. Maria Lopez", "Fall"),
    ("MA201", "Linear Algebra", 2, 3, "Dr. Maria Lopez", "Spring"),
    ("MA301", "Probability", 2, 3, "Dr. Omar Haddad", "Spring"),
    ("PH101", "Mechanics", 3, 4, "Dr. Lena Novak", "Fall"),
    ("PH201", "Electromagnetism", 3, 4, "Dr. Lena Novak", "Spring"),
    ("EC101", "Microeconomics", 4, 3, "Dr. Raj Mehta", "Fall"),
    ("EC201", "Macroeconomics", 4, 3, "Dr. Raj Mehta", "Spring"),
    ("HI101", "World History", 5, 2, "Dr. Clara Brooks", "Fall"),
    ("HI301", "Medieval Europe", 5, 2, "Dr. Clara Brooks", "Spring"),  # nobody enrolls
]

FIRST_NAMES_M = ["Arjun", "Liam", "Noah", "Ravi", "Omar", "Lucas", "Ethan", "Kenji",
                 "Mateo", "Samuel", "Daniel", "Ivan", "Hugo", "Aditya", "Felix"]
FIRST_NAMES_F = ["Priya", "Emma", "Olivia", "Aisha", "Sofia", "Mia", "Yuki", "Ananya",
                 "Chloe", "Zara", "Hannah", "Elena", "Grace", "Meera", "Lily"]
LAST_NAMES = ["Sharma", "Smith", "Khan", "Garcia", "Chen", "Patel", "Brown", "Tanaka",
              "Silva", "Müller", "Rossi", "Kumar", "Wilson", "Ahmed", "Novak", "Das",
              "Martin", "Lee", "Singh", "Clark"]
CITIES = ["Mumbai", "Delhi", "London", "New York", "Tokyo", "Berlin", "Toronto", "Sydney"]

N_STUDENTS = 50
UNENROLLED_STUDENTS = 3   # students with no marks rows at all
NULL_SCORE_RATE = 0.06    # share of enrollments not graded yet
NULL_EMAIL_RATE = 0.15


def random_date(rng: random.Random, start: date, end: date) -> str:
    return (start + timedelta(days=rng.randint(0, (end - start).days))).isoformat()


def build(db_path: Path = DB_PATH, seed: int = SEED) -> Path:
    rng = random.Random(seed)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.executemany("INSERT INTO departments VALUES (?, ?, ?)", DEPARTMENTS)
    conn.executemany(
        "INSERT INTO courses (course_id, code, title, dept_id, credits, instructor, semester) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(i, *c) for i, c in enumerate(COURSES, start=1)],
    )

    students = []
    for sid in range(1, N_STUDENTS + 1):
        gender = rng.choice("MF")
        first = rng.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
        last = rng.choice(LAST_NAMES)
        year = rng.randint(1, 4)
        email = None if rng.random() < NULL_EMAIL_RATE else f"{first.lower()}.{last.lower()}{sid}@uni.edu"
        dob = random_date(rng, date(2001, 1, 1), date(2007, 12, 31))
        students.append((sid, first, last, gender, rng.randint(1, 5), year, rng.choice(CITIES), email, dob))
    conn.executemany("INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", students)

    enrollable_courses = list(range(1, len(COURSES)))  # last course (HI301) gets no enrollments
    unenrolled = set(rng.sample(range(1, N_STUDENTS + 1), UNENROLLED_STUDENTS))
    marks = []
    for sid, *_rest in students:
        if sid in unenrolled:
            continue
        dept_id = _rest[3]
        home = [cid for cid in enrollable_courses if COURSES[cid - 1][2] == dept_id]
        other = [cid for cid in enrollable_courses if cid not in home]
        picks = set(rng.sample(home, k=min(len(home), rng.randint(1, 2))))
        picks |= set(rng.sample(other, k=rng.randint(1, 3)))
        for cid in sorted(picks):
            semester = COURSES[cid - 1][5]
            exam = (random_date(rng, date(2025, 12, 1), date(2025, 12, 20)) if semester == "Fall"
                    else random_date(rng, date(2026, 5, 1), date(2026, 5, 25)))
            score = None if rng.random() < NULL_SCORE_RATE else round(min(100, max(20, rng.gauss(68, 14))), 1)
            marks.append((sid, cid, score, exam))
    conn.executemany(
        "INSERT INTO marks (student_id, course_id, score, exam_date) VALUES (?, ?, ?, ?)", marks
    )
    conn.commit()
    conn.close()
    return db_path


if __name__ == "__main__":
    path = build()
    with sqlite3.connect(path) as c:
        for table in ("departments", "students", "courses", "marks"):
            print(f"{table:12s} {c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:>4d} rows")
    print(f"Wrote {path}")
