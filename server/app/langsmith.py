"""Read-only LangSmith client — authoritative source for tokens + latency (ADR-0003)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class RunMetrics:
    prompt_tokens: int
    input_tokens: int
    output_tokens: int
    ttft_ms: int | None


def fetch_run_metrics(base_url: str, run_id: str, api_key: str | None = None) -> RunMetrics:
    headers = {"x-api-key": api_key} if api_key else {}
    resp = httpx.get(f"{base_url}/runs/{run_id}", headers=headers, timeout=10.0)
    resp.raise_for_status()
    j = resp.json()
    ttft = j.get("ttft_ms")
    return RunMetrics(
        prompt_tokens=int(j.get("prompt_tokens", 0)),
        input_tokens=int(j.get("input_tokens", 0)),
        output_tokens=int(j.get("output_tokens", 0)),
        ttft_ms=None if ttft is None else int(ttft),
    )
