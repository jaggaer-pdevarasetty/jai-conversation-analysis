"""Gemini classifier — boundary mocked (no live calls)."""

import httpx
import pytest

from app import gemini
from app.fixtures import CONVERSATIONS


def _gemini_reply(category: str) -> dict:
    text = '{"category": "%s", "rationale": "because"}' % category
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_uses_gemini_label_when_valid(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Response(200, json=_gemini_reply("out_of_scope"), request=httpx.Request("POST", url))
    )
    rec = gemini.classify_with_gemini(CONVERSATIONS[0], "run", "2026-01-01T00:00:00Z", api_key="k")
    assert rec.model_category == "out_of_scope"
    assert rec.analyzer_version.startswith("gemini:")


def test_falls_back_to_rules_on_invalid_label(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Response(200, json=_gemini_reply("not_a_category"), request=httpx.Request("POST", url))
    )
    rec = gemini.classify_with_gemini(CONVERSATIONS[0], "run", "2026-01-01T00:00:00Z", api_key="k")
    assert rec.model_category in {
        "resolved",
        "failed_to_resolve",
        "positive_feedback",
        "negative_feedback",
        "out_of_scope",
    }


def test_raises_on_api_failure_so_run_retries(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Response(503, request=httpx.Request("POST", url))
    )
    with pytest.raises(httpx.HTTPStatusError):
        gemini.classify_with_gemini(CONVERSATIONS[0], "run", "2026-01-01T00:00:00Z", api_key="k")


def test_make_classifier_defaults_to_rules_without_key():
    # settings.gemini_api_key is empty in tests → deterministic rules.
    assert gemini.make_classifier().__name__ == "analyze"
