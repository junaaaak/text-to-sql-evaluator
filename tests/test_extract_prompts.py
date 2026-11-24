import pytest

from src.extract import extract_sql
from src.prompts import PROMPT_STYLES, build_messages


@pytest.mark.parametrize("reply,expected", [
    ("SELECT COUNT(*) FROM students;", "SELECT COUNT(*) FROM students"),
    ("```sql\nSELECT name FROM departments;\n```", "SELECT name FROM departments"),
    ("```\nSELECT 1\n```", "SELECT 1"),
    ("Here is the query:\n```sql\nSELECT a\nFROM t\n```\nThis counts rows.", "SELECT a\nFROM t"),
    ("Sure! SELECT city FROM students; This lists cities.", "SELECT city FROM students"),
    ("SELECT name FROM t WHERE name = 'a;b';", "SELECT name FROM t WHERE name = 'a;b'"),
    ("WITH x AS (SELECT 1) SELECT * FROM x", "WITH x AS (SELECT 1) SELECT * FROM x"),
    ("SELECT 1\n\nThis query returns one.", "SELECT 1"),
    ("SELECT 1; SELECT 2;", "SELECT 1"),
    ("I cannot answer that.", ""),
    ("", ""),
    (None, ""),
])
def test_extract_sql(reply, expected):
    assert extract_sql(reply) == expected


@pytest.mark.parametrize("style", PROMPT_STYLES)
def test_prompts_contain_schema_and_question(style):
    messages = build_messages(style, "How many students are there?")
    text = "\n".join(m["content"] for m in messages)
    assert "CREATE TABLE marks" in text
    assert messages[-1]["role"] == "user"
    assert "How many students are there?" in messages[-1]["content"]


def test_schema_hints_include_values():
    text = build_messages("schema_hints", "q")[-1]["content"]
    assert "'Computer Science'" in text and "Sample rows" in text


def test_unknown_style():
    with pytest.raises(ValueError):
        build_messages("nope", "q")
