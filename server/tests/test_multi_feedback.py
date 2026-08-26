"""Multi-feedback capture + root-cause/knowledge-gap grouping + impact (ADR-0022)."""

import json
from dataclasses import asdict

from fastapi.testclient import TestClient

from app import gemini
from app.deidentify import deidentify
from app.domain.analyze import analyze as rules_analyze
from app.domain.models import CommonConversation, Conversation, Enrichment, Feedback, Message
from app.main import app
from app.store_sql import _row_to_conv

client = TestClient(app)


def _conv(**kw) -> Conversation:
    base = dict(
        id="c1", tenant_id="t", title=None, created_at="2020-01-01T00:00:00",
        messages=[Message(id="m1", role="assistant", content="ans", sequence_num=1)],
        feedback=Feedback(),
    )
    base.update(kw)
    return Conversation(**base)


# ── Part A: capture all feedback ────────────────────────────────────────────
def test_deidentify_keeps_all_feedback_scrubbed():
    conv = _conv(
        feedback=Feedback(rating=False, comment="bad, email john@acme.com", message_id="m1"),
        feedbacks=[
            Feedback(rating=False, comment="bad, email john@acme.com", message_id="m1"),
            Feedback(rating=True, comment="great now", message_id="m2"),
        ],
        user_id="u-123",
    )
    cc = deidentify(conv)
    assert len(cc.feedbacks) == 2
    assert all("john@acme.com" not in (f.comment or "") for f in cc.feedbacks)  # PII scrubbed
    assert [f.message_id for f in cc.feedbacks] == ["m1", "m2"]  # tied to their turns


def test_store_roundtrips_all_feedback():
    cc = CommonConversation(
        conversation_id="c1", messages=[], environment="uit",
        feedback=Feedback(rating=False, comment="x", message_id="m1"),
        feedbacks=[
            Feedback(rating=False, comment="x", message_id="m1"),
            Feedback(rating=True, comment="y", message_id="m2"),
        ],
    )
    out = _row_to_conv(asdict(cc))
    assert len(out.feedbacks) == 2 and out.feedbacks[1].rating is True


def test_store_backcompat_row_without_feedbacks_key():
    # Legacy row (pre-ADR-0022) has no "feedbacks" → fall back to the single primary.
    data = {
        "conversation_id": "c1", "environment": "uit", "messages": [],
        "feedback": {"rating": False, "comment": "x", "message_id": "m1"},
    }
    out = _row_to_conv(data)
    assert len(out.feedbacks) == 1 and out.feedbacks[0].rating is False


# ── Part B: root cause + user_hash + grouping ───────────────────────────────
def test_deep_analyze_sets_root_cause_and_feeds_all_feedback():
    conv = _conv(
        feedback=Feedback(rating=False, comment="wrong doc", message_id="m1"),
        feedbacks=[
            Feedback(rating=False, comment="wrong doc", message_id="m1"),
            Feedback(rating=False, comment="still the wrong form", message_id="m2"),
        ],
    )
    captured: dict = {}

    def gen(prompt: str) -> str:
        captured["p"] = prompt
        return json.dumps({
            "what_happened": "x", "why_it_happened": "y", "how_to_avoid": "z",
            "suggestions": "s", "root_cause": "wrong_document_retrieved",
        })

    da = gemini.deep_analyze(conv, generate=gen)
    assert da.root_cause == "wrong_document_retrieved"
    assert "still the wrong form" in captured["p"]  # ALL feedback reached the prompt


def test_deep_analyze_root_cause_falls_back_to_signals():
    conv = _conv(
        feedback=Feedback(rating=False, comment="x", message_id="m1"),
        enrichment=Enrichment(langsmith_found=True, retrieval_hit=False),
    )
    da = gemini.deep_analyze(conv, generate=lambda _p: json.dumps({"root_cause": "bogus"}))
    assert da.root_cause == "knowledge_gap"  # invalid label → derived from the retrieval miss


def test_user_hash_is_pseudonymised_never_raw():
    rec = rules_analyze(_conv(user_id="user-9999"), "run")
    assert rec.user_hash.startswith("user-")
    assert "9999" not in rec.user_hash  # one-way hash, not the raw id


def test_groups_endpoint_is_impact_ranked():
    res = client.get("/api/analysis/groups")
    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "issues" and "items" in body and "total" in body
    for g in body["items"]:
        assert {"root_cause", "label", "conversations", "tenants", "users", "knowledge_gap"} <= set(g)
    counts = [g["conversations"] for g in body["items"]]
    assert counts == sorted(counts, reverse=True)  # biggest impact first


def test_groups_scope_validation():
    assert client.get("/api/analysis/groups?scope=all").status_code == 200
    assert client.get("/api/analysis/groups?scope=bogus").status_code == 422


def test_feedback_accepts_root_cause_drill_in_filter():
    assert client.get("/api/analysis/feedback?root_cause=knowledge_gap").status_code == 200
