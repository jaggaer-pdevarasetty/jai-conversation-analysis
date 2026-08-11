"""Vertex classifier — SDK boundary injected (no live calls, no SDK needed)."""

import pytest

from app import gemini
from app.fixtures import CONVERSATIONS


def test_uses_vertex_label_when_valid():
    rec = gemini.classify_with_vertex(
        CONVERSATIONS[0], "run", "2026-01-01T00:00:00Z",
        generate=lambda _p: '{"category": "out_of_scope", "rationale": "because"}',
    )
    assert rec.model_category == "out_of_scope"
    assert rec.analyzer_version.startswith("vertex:")


def test_falls_back_to_rules_on_invalid_label():
    rec = gemini.classify_with_vertex(
        CONVERSATIONS[0], "run", "2026-01-01T00:00:00Z",
        generate=lambda _p: '{"category": "not_a_category"}',
    )
    assert rec.model_category in {
        "resolved",
        "failed_to_resolve",
        "positive_feedback",
        "negative_feedback",
        "out_of_scope",
    }


def test_raises_on_api_failure_so_run_retries():
    def boom(_p):
        raise RuntimeError("vertex unavailable")

    with pytest.raises(RuntimeError):
        gemini.classify_with_vertex(CONVERSATIONS[0], "run", "2026-01-01T00:00:00Z", generate=boom)


def test_make_classifier_defaults_to_rules_without_vertex_config():
    # conftest clears Vertex env → not configured → deterministic rules.
    assert gemini.make_classifier().__name__ == "analyze"
