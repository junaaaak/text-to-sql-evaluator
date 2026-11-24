"""Turn a run log into results/report.md and charts in results/charts/.

Usage:
    python -m src.analyze                       # latest file in results/runs/
    python -m src.analyze results/final_run.jsonl
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.benchmark import DIFFICULTIES  # noqa: E402
from src.db import ROOT  # noqa: E402
from src.prompts import PROMPT_STYLES  # noqa: E402

RESULTS_DIR = ROOT / "results"
CHART_DIR = RESULTS_DIR / "charts"

# Categorical palette, assigned in fixed order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

STATUS_GROUPS = {
    "correct": "Correct",
    "wrong_result": "Wrong result",
    "schema_error": "Schema error",
    "syntax_error": "Syntax error",
    "execution_error": "Other error",
    "timeout": "Other error",
    "no_sql": "Other error",
}
STATUS_ORDER = ["Correct", "Wrong result", "Schema error", "Syntax error", "Other error"]


def load(path: Path) -> pd.DataFrame:
    df = pd.read_json(path, lines=True)
    df["config"] = df["model"] + " / " + df["prompt_style"]
    return df


def pct(series: pd.Series) -> float:
    return round(100 * series.mean(), 1)


# ---------------------------------------------------------------------- tables

def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["model", "prompt_style"], sort=False)
    out = pd.DataFrame({
        "accuracy_%": g["correct"].apply(pct),
        "failed_to_run_%": g["failed_to_run"].apply(pct),
        "median_latency_s": g["latency_s"].median().round(2),
        "p95_latency_s": g["latency_s"].quantile(0.95).round(2),
        "avg_prompt_tokens": g["prompt_tokens"].mean().round(0).astype(int),
        "avg_completion_tokens": g["completion_tokens"].mean().round(1),
    })
    return out.reset_index()


def difficulty_table(df: pd.DataFrame) -> pd.DataFrame:
    t = df.pivot_table(index=["model", "prompt_style"], columns="difficulty",
                       values="correct", aggfunc=pct, sort=False)
    return t[[d for d in DIFFICULTIES if d in t.columns]].reset_index()


def status_table(df: pd.DataFrame) -> pd.DataFrame:
    t = pd.crosstab([df["model"], df["prompt_style"]], df["status"])
    return t.reset_index()


def type_table(df: pd.DataFrame) -> pd.DataFrame:
    t = df.pivot_table(index="question_type", columns="model", values="correct", aggfunc=pct)
    t["all_configs"] = df.groupby("question_type")["correct"].apply(pct)
    t["n_questions"] = df.groupby("question_type")["question_id"].nunique()
    return t.sort_values("all_configs").reset_index()


def hardest_questions(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    g = df.groupby(["question_id", "difficulty", "question_type", "question"])
    t = g["correct"].agg(correct_configs="sum", total_configs="count").reset_index()
    return t.sort_values(["correct_configs", "question_id"]).head(n)


def failure_examples(df: pd.DataFrame, n: int = 6) -> pd.DataFrame:
    wrong = df[~df["correct"]].copy()
    wrong["error"] = wrong["error"].fillna("").astype(str).str.slice(0, 60)
    wrong["pred_sql"] = (wrong["pred_sql"].fillna("").astype(str)
                         .str.replace(r"\s+", " ", regex=True).str.slice(0, 120))
    cols = ["question_id", "model", "prompt_style", "status", "pred_sql", "error"]
    return wrong.drop_duplicates("question_id").head(n)[cols]


# ---------------------------------------------------------------------- charts

def _style(ax, title: str, ylabel: str | None = None):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=12, pad=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_2)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _rounded_bar(ax, x, h, w, color, horizontal=False):
    bars = (ax.barh if horizontal else ax.bar)(x, h, w, color=color, edgecolor=SURFACE, linewidth=2)
    return bars


def chart_difficulty(df: pd.DataFrame, path: Path) -> None:
    models = list(dict.fromkeys(df["model"]))
    styles = [s for s in PROMPT_STYLES if s in set(df["prompt_style"])]
    fig, axes = plt.subplots(1, len(models), figsize=(5.2 * len(models), 4), sharey=True,
                             facecolor=SURFACE, squeeze=False)
    width = 0.8 / len(styles)
    for ax, model in zip(axes[0], models):
        sub = df[df["model"] == model]
        for i, style in enumerate(styles):
            vals = [pct(sub[(sub["prompt_style"] == style) & (sub["difficulty"] == d)]["correct"])
                    for d in DIFFICULTIES]
            xs = [j + (i - (len(styles) - 1) / 2) * width for j in range(len(DIFFICULTIES))]
            _rounded_bar(ax, xs, vals, width, SERIES[i])
        ax.set_xticks(range(len(DIFFICULTIES)), [d.capitalize() for d in DIFFICULTIES])
        ax.set_ylim(0, 100)
        _style(ax, model, "Execution accuracy (%)" if ax is axes[0][0] else None)
    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[i]) for i in range(len(styles))]
    fig.legend(handles, styles, loc="upper right", ncol=len(styles), frameon=False,
               labelcolor=INK_2)
    fig.suptitle("Accuracy by difficulty and prompt style", x=0.01, ha="left", color=INK,
                 fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def chart_status(df: pd.DataFrame, path: Path) -> None:
    grouped = df.assign(group=df["status"].map(STATUS_GROUPS))
    configs = list(dict.fromkeys(grouped["config"]))
    shares = (pd.crosstab(grouped["config"], grouped["group"], normalize="index") * 100) \
        .reindex(index=configs, columns=STATUS_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(configs) + 1.6), facecolor=SURFACE)
    left = pd.Series(0.0, index=configs)
    ys = range(len(configs))[::-1]
    for i, group in enumerate(STATUS_ORDER):
        ax.barh(list(ys), shares[group], 0.6, left=left, color=SERIES[i], edgecolor=SURFACE,
                linewidth=2, label=group)
        left += shares[group]
    ax.set_yticks(list(ys), configs)
    ax.set_xlim(0, 100)
    _style(ax, "Outcome of every generated query (% of questions)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=len(STATUS_ORDER),
              frameon=False, labelcolor=INK_2)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def chart_types(types: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(types) + 1.2), facecolor=SURFACE)
    ys = range(len(types))
    ax.barh(list(ys), types["all_configs"], 0.6, color=SERIES[0], edgecolor=SURFACE, linewidth=2)
    for y, v in zip(ys, types["all_configs"]):
        ax.text(v + 1, y, f"{v:.0f}%", va="center", color=INK_2, fontsize=9)
    labels = [f"{t} ({n})" for t, n in zip(types["question_type"], types["n_questions"])]
    ax.set_yticks(list(ys), labels)
    ax.set_xlim(0, 108)
    _style(ax, "Accuracy by question type, all models and prompts (number of questions)")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------------- report

def _md(t: pd.DataFrame) -> str:
    return t.to_markdown(index=False)


def write_report(df: pd.DataFrame, source: Path) -> Path:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    types = type_table(df)
    chart_difficulty(df, CHART_DIR / "accuracy_by_difficulty.png")
    chart_status(df, CHART_DIR / "outcomes.png")
    chart_types(types, CHART_DIR / "accuracy_by_type.png")

    summary = summary_table(df)
    best = summary.sort_values(["accuracy_%", "median_latency_s"], ascending=[False, True]).iloc[0]
    worst_type = types.iloc[0]
    n_q = df["question_id"].nunique()
    try:
        source_label = source.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        source_label = source.name

    lines = [
        "# Results",
        "",
        f"Source: `{source_label}` — {n_q} questions × "
        f"{df['model'].nunique()} models × {df['prompt_style'].nunique()} prompt styles "
        f"= {len(df)} generated queries. Temperature 0, seed 42.",
        "",
        "## Key findings",
        "",
        f"- **Best configuration:** {best['model']} with the `{best['prompt_style']}` prompt — "
        f"{best['accuracy_%']}% execution accuracy, {best['failed_to_run_%']}% of queries failed to run.",
        f"- **Hardest question type:** `{worst_type['question_type']}` — "
        f"{worst_type['all_configs']}% accuracy across all configurations.",
        f"- **Overall failed-to-run rate:** {pct(df['failed_to_run'])}% "
        f"(most common error: `{df[df['failed_to_run']]['status'].mode().iat[0] if df['failed_to_run'].any() else 'none'}`).",
        "",
        "## Summary by model and prompt",
        "",
        _md(summary),
        "",
        "## Accuracy by difficulty (%)",
        "",
        "![Accuracy by difficulty](charts/accuracy_by_difficulty.png)",
        "",
        _md(difficulty_table(df)),
        "",
        "## Outcomes",
        "",
        "![Outcomes](charts/outcomes.png)",
        "",
        _md(status_table(df)),
        "",
        "## Accuracy by question type (%)",
        "",
        "![Accuracy by question type](charts/accuracy_by_type.png)",
        "",
        _md(types),
        "",
        "## Hardest questions",
        "",
        _md(hardest_questions(df)),
        "",
        "## Example failures",
        "",
        _md(failure_examples(df)),
        "",
    ]
    report = RESULTS_DIR / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def latest_run() -> Path:
    runs = sorted((RESULTS_DIR / "runs").glob("run_*.jsonl"))
    if not runs:
        sys.exit("No run files in results/runs/. Run `python -m src.run_eval` first.")
    return runs[-1]


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    data = load(src)
    print(summary_table(data).to_string(index=False))
    print(f"\nWrote {write_report(data, src)}")
