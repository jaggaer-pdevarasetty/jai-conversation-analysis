"""Multi-feedback capture + root-cause/knowledge-gap grouping + impact (ADR-0022)."""

import json
from dataclasses import asdict

from fastapi.testclient import TestClient

from app import gemini, main as main_module
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


def test_feedback_endpoint_returns_one_row_per_rated_message(monkeypatch):
    source = _conv(
        id="multi-rated",
        feedback=Feedback(rating=False, comment="first", message_id="m1"),
        feedbacks=[
            Feedback(rating=False, comment="first", message_id="m1"),
            Feedback(rating=False, comment="second", message_id="m2"),
            Feedback(rating=True, comment="fixed", message_id="m3"),
        ],
        messages=[
            Message(id="m1", role="assistant", content="a", sequence_num=1, created_at="2026-10-01T10:00:00+00:00"),
            Message(id="m2", role="assistant", content="b", sequence_num=2, created_at="2026-10-01T10:01:00+00:00"),
            Message(id="m3", role="assistant", content="c", sequence_num=3, created_at="2026-10-01T10:02:00+00:00"),
        ],
    )
    record = rules_analyze(source, "run")
    record.enrichment = Enrichment(
        agent_used="rag", platform="JI", interaction_mode="Ask", langsmith_found=True
    )
    common = deidentify(source)
    calls = []
    monkeypatch.setattr(
        main_module.store,
        "list",
        lambda region=None, env="uit": calls.append(("list", env)) or [record],
    )
    monkeypatch.setattr(
        main_module.store,
        "get_conversations",
        lambda ids, env="uit": calls.append(("conversations", env)) or {source.id: common},
    )
    monkeypatch.setattr(
        "app.dashboard.conversation_meta",
        lambda ids, region=None, env="uit": calls.append(("meta", env)) or {source.id: {"title": "Three ratings"}},
    )

    body = client.get("/api/analysis/feedback?env=prod&limit=100").json()

    assert body["total"] == 3
    assert body["scope_total"] == 3
    assert body["negative"] == 2
    assert body["positive"] == 1
    assert {item["feedback_message_id"] for item in body["items"]} == {"m1", "m2", "m3"}
    assert len({item["feedback_id"] for item in body["items"]}) == 3
    assert {item["platform"] for item in body["items"]} == {"JI"}
    assert {item["interaction_mode"] for item in body["items"]} == {"Ask"}
    assert calls == [("list", "prod"), ("conversations", "prod"), ("meta", "prod")]


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


def test_attention_signals_route_to_insights_groups():
    guardrail = rules_analyze(_conv(), "run")
    guardrail.signals.guardrail_bypass = True
    guardrail.signals.immediate_attention = True
    assert main_module._record_root_cause(guardrail) == "guardrail_bypass"

    kb = rules_analyze(_conv(), "run")
    kb.signals.kb_issue = True
    assert main_module._record_root_cause(kb) == "knowledge_gap"


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
