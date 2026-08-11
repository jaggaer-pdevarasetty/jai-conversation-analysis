"""Boundary-mocked integration: mock the LangSmith HTTP API (httpx MockTransport)
and assert our client parses authoritative token/latency metrics (ADR-0003)."""

import httpx
import pytest

from app import langsmith


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_run_metrics_parses_tokens_and_ttft(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/runs/run-1"
        return httpx.Response(
            200,
            json={"prompt_tokens": 120, "input_tokens": 130, "output_tokens": 48, "ttft_ms": 340},
        )

    monkeypatch.setattr(httpx, "get", lambda url, **kw: _mock_client(handler).get(url))
    m = langsmith.fetch_run_metrics("https://ls.test", "run-1")
    assert (m.prompt_tokens, m.input_tokens, m.output_tokens, m.ttft_ms) == (120, 130, 48, 340)


def test_fetch_run_metrics_raises_on_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    monkeypatch.setattr(httpx, "get", lambda url, **kw: _mock_client(handler).get(url))
    with pytest.raises(httpx.HTTPStatusError):
        langsmith.fetch_run_metrics("https://ls.test", "run-err")
