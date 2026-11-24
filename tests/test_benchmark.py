from collections import Counter

from src import grader
from src.benchmark import load_questions, validate
from src.db import connect_readonly


def test_benchmark_is_valid():
    questions = load_questions()
    assert Counter(q.difficulty for q in questions) == {"easy": 15, "medium": 15, "hard": 15}
    assert validate(questions) == []


def test_every_gold_query_grades_itself_correct():
    conn = connect_readonly()
    for q in load_questions():
        assert grader.grade(conn, q.gold_sql, q.gold_sql).correct, q.id
