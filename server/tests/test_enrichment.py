"""LangSmith enrichment: extract only SAFE fields; never leak JWT/URLs/PII (ADR-0018)."""

from app import enrichment
from app.enrichment import build_enrichment, fetch_enrichment

# A realistic LangSmith run that INCLUDES the dangerous stuff we must never surface.
JWT = "eyJhbGciOiJSUzI1NiJ9.eyJ0ZW5hbnRfaWQiOiIyMDAyMDAwMDgwOCJ9.sig"
DIRTY_RUN = {
    "run_type": "chain",
    "name": "knowledge_search | 20020000808",
    "tags": ["intent:knowledge_search", "agent:rag", "confidence:ConfidenceLevel.HIGH", "response_type:answer"],
    "inputs": {
        "intent": "knowledge_search",
        "secondary_intent": None,
        "reasoning": "User john.doe@buffalo.edu at Crofts Hall asked about req 12345678 for $3,703.85.",
        "app_context": {"api_domains": {"JI": "https://ji-us-uit-api-internal.example/secret"}},
        "user_query": "how do I approve",
    },
    "outputs": {
        "agent_used": "rag",
        "response_type": "answer",
        "confidence": "HIGH",
        "has_error": False,
        "frustration_score": 0.1,
        "turn_count": 3,
        "citations": [
            {"citation_number": 1, "file_name": "administrative-services_shopblue_assign-approver.html",
             "snippet": "contact jane.roe@buffalo.edu"},
        ],
    },
    "extra": {"metadata": {"_user_jwt_token": JWT, "tenant_id": "20020000808", "user_id": "9464669"}},
}


def _flat(e) -> str:
    from dataclasses import asdict
    return str(asdict(e))


def test_extracts_safe_signals():
    e = build_enrichment([DIRTY_RUN])
    assert e.intent == "knowledge_search"
    assert e.agent_used == "rag"
    assert e.response_type == "answer"
    assert e.source_confidence == "HIGH"
    assert e.retrieval_hit is True and e.retrieved_count == 1
    assert e.retrieved_docs and "assign-approver" in e.retrieved_docs[0]
    assert e.had_error is False
    assert e.langsmith_found is True


def test_no_secret_or_pii_survives():
    e = build_enrichment([DIRTY_RUN])
    blob = _flat(e)
    # secrets / internal urls must never appear
    assert JWT not in blob and "_user_jwt_token" not in blob
    assert "api-internal" not in blob and "https://" not in blob
    # personal data in the reasoning must be scrubbed
    for leak in ("john.doe@buffalo.edu", "jane.roe@buffalo.edu", "12345678", "3,703.85"):
        assert leak not in blob, f"{leak!r} leaked into enrichment"
    # the reasoning is still present, just scrubbed
    assert "[email]" in e.reasoning_summary or "[id]" in e.reasoning_summary or "[amount]" in e.reasoning_summary


def test_fetch_disabled_returns_none():
    # No LangSmith key configured in tests → enrichment is off → None, never a network call.
    assert fetch_enrichment("some-id", "us") is None


def test_fetch_never_raises_on_bad_project(monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(
        enrichment_enabled=True, langsmith_api_key="k",
        langsmith_base_url="https://x", enrichment_max_runs=5,
        langsmith_project_for=lambda region: "uit_us",
    )
    monkeypatch.setattr(enrichment, "settings", fake)
    monkeypatch.setattr(enrichment, "_project_id", lambda name: None)  # project not found
    assert fetch_enrichment("id", "us") is None
