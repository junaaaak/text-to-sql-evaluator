"""Chat with the school database in plain English.

Run:  streamlit run app/chat.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import QueryTimeout, connect_readonly, run_query, schema_text  # noqa: E402
from src.extract import extract_sql  # noqa: E402
from src.grader import classify_error  # noqa: E402
from src.llm import generate  # noqa: E402
from src.prompts import PROMPT_STYLES, build_messages  # noqa: E402
from src.run_eval import DEFAULT_MODELS  # noqa: E402

EXAMPLES = [
    "How many students are in each department?",
    "Which courses have an average score below 65?",
    "Who got the highest score in Calculus I?",
    "List students who are not enrolled in any course.",
]

st.set_page_config(page_title="Text-to-SQL Chat", page_icon="🗄️", layout="wide")


@st.cache_resource
def get_conn():
    return connect_readonly()


def installed_models() -> list[str]:
    try:
        import ollama

        names = [m.model for m in ollama.list().models]
    except Exception:  # noqa: BLE001 - Ollama not running
        return []
    preferred = [m for m in DEFAULT_MODELS if m in names]
    return preferred + [n for n in names if n not in preferred]


def answer(question: str, model: str, style: str) -> dict:
    gen = generate(model, build_messages(style, question))
    sql = extract_sql(gen.text)
    out = {"question": question, "sql": sql, "raw": gen.text, "latency": gen.latency_s,
           "tokens": gen.prompt_tokens + gen.completion_tokens, "rows": None, "error": None}
    if not sql:
        out["error"] = "The model did not return a SQL query."
        return out
    try:
        res = run_query(get_conn(), sql)
        out["rows"] = pd.DataFrame(res.rows, columns=res.columns)
    except (QueryTimeout, Exception) as exc:  # noqa: BLE001 - shown to the user
        out["error"] = f"{classify_error(exc).replace('_', ' ')}: {exc}"
    return out


def show(turn: dict) -> None:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.code(turn["sql"] or turn["raw"], language="sql")
        if turn["error"]:
            st.error(turn["error"])
        elif turn["rows"] is not None:
            st.dataframe(turn["rows"], hide_index=True, width="stretch")
            st.caption(f"{len(turn['rows'])} row(s)")
        st.caption(f"{turn['latency']:.2f}s · {turn['tokens']} tokens")


models = installed_models()
with st.sidebar:
    st.header("Settings")
    if not models:
        st.error("Ollama is not running or has no models. Start Ollama and run "
                 "`ollama pull qwen2.5-coder:3b`.")
        st.stop()
    model = st.selectbox("Model", models)
    # few_shot had the best accuracy in the evaluation (see results/report.md).
    style = st.selectbox("Prompt style", PROMPT_STYLES, index=PROMPT_STYLES.index("few_shot"))
    if st.button("Clear chat"):
        st.session_state.history = []
    st.subheader("Try an example")
    clicked = next((q for q in EXAMPLES if st.button(q, width="stretch")), None)
    with st.expander("Database schema"):
        st.code(schema_text(), language="sql")

st.title("Ask the school database")
st.caption("Questions about students, departments, courses and marks are turned into SQL "
           "and run against a read-only SQLite database.")

st.session_state.setdefault("history", [])

for turn in st.session_state.history:
    show(turn)

question = st.chat_input("Ask a question, e.g. 'Which city has the most students?'") or clicked
if question:
    with st.spinner("Writing SQL ..."):
        turn = answer(question, model, style)
    st.session_state.history.append(turn)
    show(turn)
