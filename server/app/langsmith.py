"""Read-only LangSmith client — authoritative source for tokens + latency (ADR-0003).

Uses the shared env-aware HTTP client so it works behind a corporate proxy/CA (Zscaler)
via REQUESTS_CA_BUNDLE + HTTPS_PROXY, without ever disabling TLS verification.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .http import client as make_client


@dataclass
class RunMetrics:
    prompt_tokens: int
    input_tokens: int
    output_tokens: int
    ttft_ms: int | None


def fetch_run_metrics(
    base_url: str, run_id: str, api_key: str | None = None, *, http_client: httpx.Client | None = None
) -> RunMetrics:
    headers = {"x-api-key": api_key} if api_key else {}
    hc = http_client or make_client()
    try:
        resp = hc.get(f"{base_url}/runs/{run_id}", headers=headers)
        resp.raise_for_status()
        j = resp.json()
    finally:
        if http_client is None:
            hc.close()
    ttft = j.get("ttft_ms")
    return RunMetrics(
        prompt_tokens=int(j.get("prompt_tokens", 0)),
        input_tokens=int(j.get("input_tokens", 0)),
        output_tokens=int(j.get("output_tokens", 0)),
        ttft_ms=None if ttft is None else int(ttft),
    )
