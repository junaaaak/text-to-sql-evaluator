"""Run every model x prompt style x question and log one JSON line per attempt.

Usage:
    python -m src.run_eval                                  # full run, default models
    python -m src.run_eval --models qwen2.5-coder:3b --prompts zero_shot --limit 5
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from src import grader
from src.benchmark import load_questions
from src.db import ROOT, connect_readonly
from src.extract import extract_sql
from src.llm import generate, model_digest, warm_up
from src.prompts import PROMPT_STYLES, build_messages

DEFAULT_MODELS = ("qwen2.5-coder:3b", "llama3.2:3b")
RUNS_DIR = ROOT / "results" / "runs"


def run(models: list[str], prompts: list[str], limit: int | None = None,
        out_path: Path | None = None, ids: list[str] | None = None) -> Path:
    questions = load_questions()
    if ids:
        questions = [q for q in questions if q.id in set(ids)]
    if limit:
        questions = questions[:limit]

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_path or RUNS_DIR / f"run_{run_id}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect_readonly()
    total = len(models) * len(prompts) * len(questions)
    done = 0
    started = time.perf_counter()

    with out_path.open("w", encoding="utf-8") as f:
        for model in models:
            print(f"Loading {model} ...", flush=True)
            warm_up(model)
            digest = model_digest(model)
            for style in prompts:
                n_correct = 0
                for q in questions:
                    gen = generate(model, build_messages(style, q.question))
                    pred_sql = extract_sql(gen.text)
                    result = grader.grade(conn, q.gold_sql, pred_sql)
                    n_correct += result.correct
                    record = {
                        "run_id": run_id, "model": model, "model_digest": digest,
                        "prompt_style": style, "question_id": q.id,
                        "difficulty": q.difficulty, "question_type": q.type,
                        "question": q.question, "gold_sql": q.gold_sql,
                        "raw_output": gen.text, "pred_sql": pred_sql,
                        "status": result.status, "correct": result.correct,
                        "failed_to_run": result.failed_to_run, "error": result.error,
                        "pred_row_count": result.pred_row_count,
                        "latency_s": round(gen.latency_s, 4),
                        "prompt_tokens": gen.prompt_tokens,
                        "completion_tokens": gen.completion_tokens,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    f.flush()
                    done += 1
                print(f"  {model:18s} {style:13s} {n_correct}/{len(questions)} correct "
                      f"[{done}/{total}, {time.perf_counter() - started:.0f}s]", flush=True)
    print(f"Wrote {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--prompts", nargs="+", default=list(PROMPT_STYLES), choices=PROMPT_STYLES)
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--ids", nargs="+", help="only these question ids")
    parser.add_argument("--out", type=Path, help="output .jsonl path")
    args = parser.parse_args()
    run(args.models, args.prompts, args.limit, args.out, args.ids)


if __name__ == "__main__":
    main()
