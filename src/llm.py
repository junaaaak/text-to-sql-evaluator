"""Thin wrapper around the Ollama chat API that records latency and token counts."""

from __future__ import annotations

import time
from dataclasses import dataclass

import ollama

DEFAULT_OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 512}


@dataclass
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float          # wall-clock time for the whole call
    load_s: float             # time Ollama spent loading the model (0 when already loaded)


def generate(model: str, messages: list[dict], options: dict | None = None,
             host: str | None = None) -> Generation:
    client = ollama.Client(host=host) if host else ollama
    start = time.perf_counter()
    response = client.chat(model=model, messages=messages,
                           options={**DEFAULT_OPTIONS, **(options or {})}, keep_alive="10m")
    latency = time.perf_counter() - start
    return Generation(
        text=response.message.content or "",
        prompt_tokens=response.prompt_eval_count or 0,
        completion_tokens=response.eval_count or 0,
        latency_s=latency,
        load_s=(response.load_duration or 0) / 1e9,
    )


def warm_up(model: str) -> None:
    """Load the model into memory so the first timed call does not include load time."""
    generate(model, [{"role": "user", "content": "SELECT 1;"}], options={"num_predict": 1})


def model_digest(model: str) -> str:
    """Short content hash of the installed model, logged for reproducibility."""
    try:
        for m in ollama.list().models:
            if m.model == model or m.model == f"{model}:latest":
                return (m.digest or "")[:12]
    except Exception:  # noqa: BLE001 - digest is informational only
        pass
    return ""
