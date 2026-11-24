import pytest

from src import grader
from src.db import connect_readonly


@pytest.fixture(scope="module")
def conn():
    return connect_readonly()


# --- results_match -------------------------------------------------------------

def test_unordered_ignores_row_order():
    assert grader.results_match([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], ordered=False)


def test_ordered_requires_row_order():
    assert not grader.results_match([(1,), (2,)], [(2,), (1,)], ordered=True)
    assert grader.results_match([(1,), (2,)], [(1,), (2,)], ordered=True)


def test_duplicates_count():
    assert not grader.results_match([("a",), ("a",)], [("a",)], ordered=False)
    assert not grader.results_match([("a",), ("b",)], [("a",), ("a",)], ordered=False)


def test_numbers_rounded_and_int_float_equal():
    assert grader.results_match([(66.666,)], [(66.67,)], ordered=False)
    assert grader.results_match([(3,)], [(3.0,)], ordered=False)
    assert not grader.results_match([(66.6,)], [(66.7,)], ordered=False)


def test_column_order_ignored():
    assert grader.results_match([("Tokyo", 4), ("Delhi", 2)], [(4, "Tokyo"), (2, "Delhi")], ordered=False)


def test_column_permutation_must_be_consistent_across_rows():
    # Swapping columns in only one row is not a valid reordering.
    assert not grader.results_match([(1, 2), (3, 4)], [(2, 1), (3, 4)], ordered=False)


def test_extra_column_is_wrong():
    assert not grader.results_match([("Tokyo",)], [("Tokyo", 4)], ordered=False)


def test_empty_results_match():
    assert grader.results_match([], [], ordered=False)


def test_none_values():
    assert grader.results_match([(None, 1)], [(None, 1)], ordered=False)


# --- ORDER BY detection --------------------------------------------------------

@pytest.mark.parametrize("sql,expected", [
    ("SELECT a FROM t ORDER BY a", True),
    ("SELECT a FROM t", False),
    ("SELECT a FROM (SELECT a FROM t ORDER BY a)", False),
    ("SELECT a, RANK() OVER (ORDER BY a) FROM t", False),
    ("SELECT a FROM t ORDER BY a DESC LIMIT 1", True),
])
def test_has_top_level_order_by(sql, expected):
    assert grader.has_top_level_order_by(sql) is expected


# --- grade() against the real database ------------------------------------------

def test_equivalent_query_is_correct(conn):
    g = grader.grade(conn, "SELECT COUNT(*) FROM students",
                     "SELECT COUNT(student_id) AS total FROM students")
    assert g.status == grader.CORRECT


def test_wrong_result(conn):
    g = grader.grade(conn, "SELECT COUNT(*) FROM students", "SELECT COUNT(*) FROM courses")
    assert g.status == grader.WRONG_RESULT and not g.failed_to_run


def test_syntax_error(conn):
    g = grader.grade(conn, "SELECT 1", "SELEC name FROM students")
    assert g.status == grader.SYNTAX_ERROR and g.failed_to_run


def test_unknown_column_is_schema_error(conn):
    g = grader.grade(conn, "SELECT 1", "SELECT student_name FROM students")
    assert g.status == grader.SCHEMA_ERROR


def test_unknown_table_is_schema_error(conn):
    g = grader.grade(conn, "SELECT 1", "SELECT * FROM enrollments")
    assert g.status == grader.SCHEMA_ERROR


def test_write_is_blocked(conn):
    g = grader.grade(conn, "SELECT 1", "DELETE FROM marks")
    assert g.status == grader.EXECUTION_ERROR
    assert grader.grade(conn, "SELECT COUNT(*) FROM marks", "SELECT COUNT(*) FROM marks").correct


def test_empty_prediction(conn):
    assert grader.grade(conn, "SELECT 1", "  ").status == grader.NO_SQL


def test_timeout(conn):
    endless = ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) "
               "SELECT COUNT(*) FROM n")
    g = grader.grade(conn, "SELECT 1", endless, timeout_s=0.5)
    assert g.status == grader.TIMEOUT
