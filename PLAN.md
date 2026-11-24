# Project Plan

## Goal
A chatbot that turns English questions about a small school database into SQL, plus an
evaluator that grades local open models by **execution accuracy**: the model's SQL is run
and its result is compared with the result of a hand-written reference query.

**Measured:** accuracy by difficulty (easy / medium / hard), % of SQL that fails to run,
latency, tokens.
**Stretch:** 3 prompt styles × 2 models; which question types fail most.

## Learning outcomes
1. Design an LLM evaluation: labelled test set, a metric that measures what matters.
2. Understand why execution accuracy beats string matching.
3. Run quantized open models locally on a 4GB GPU with Ollama.
4. Compare prompt strategies with measurements instead of intuition.
5. Practise SQL from simple filters to window functions and anti-joins.
6. Run reproducible experiments (temperature 0, fixed seeds, logged versions).
7. Analyse failures by category and question type.
8. Ship a complete, tested project with a demo UI.

## Tech stack
| Layer | Tool |
|---|---|
| Language | Python 3.12, venv |
| Database | SQLite (`sqlite3`) |
| Model runtime | Ollama + `ollama` Python client |
| Models | `qwen2.5-coder:3b` (code-tuned) vs `llama3.2:3b` (general) |
| SQL parsing | `sqlglot` |
| Analysis | `pandas`, `matplotlib` |
| UI | `streamlit` |
| Tests | `pytest` |

## Flow
```
questions.jsonl ─┐
schema ──────────┼─► prompt builder (3 styles) ─► Ollama model ─► SQL extractor
                 │                                                    │
                 │          school.db (read-only, timeout)            ▼
                 └─ gold SQL ─────────────► grader ◄────────── predicted SQL
                                              │
                         correct / wrong_result / syntax_error /
                         schema_error / timeout / no_sql
                                              ▼
                               results/runs/*.jsonl ─► analysis ─► report.md + charts
```

## Phases
| # | Phase | Done when |
|---|---|---|
| 0 | Setup: venv, requirements, repo | dependencies install |
| 1 | Database: schema + deterministic seed | `school.db` rebuilds identically |
| 2 | Benchmark: 45 questions (15 per difficulty) with gold SQL and type | validator passes |
| 3 | Grader: result comparison, error categories, unit tests | `pytest` passes |
| 4 | Inference: prompts, Ollama client, SQL extractor | one question → SQL + stats |
| 5 | Experiments: 2 models × 3 prompts × 45 questions | results file |
| 6 | Analysis: tables, charts, failure analysis | `results/report.md` |
| 7 | Chatbot: Streamlit app | demo runs |
| 8 | README with results | repo ready to share |

## Grading rules
- Rows compared as a multiset, unless the gold query has a top-level `ORDER BY`.
- Floats rounded to 2 decimals; column names ignored; column order matters.
- Database opened read-only; each query has a time limit.
