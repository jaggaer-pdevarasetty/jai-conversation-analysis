from fastapi.testclient import TestClient

from app import main as main_module
from app.domain.models import CATEGORIES
from app.main import app

client = TestClient(app)

POSITIVE_ID = "33333333-3333-4333-8333-333333333333"
NON_ENGLISH_MISSING_TELEMETRY_ID = "66666666-6666-4666-8666-666666666666"


def test_list_returns_items_counts_and_unanalysed():
    res = client.get("/api/analysis/conversations")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] and isinstance(body["counts"], dict)
    assert body["total"] > 0
    assert "unanalysed" in body


def test_list_and_detail_never_expose_tenant_or_user():
    """Attribution NFR / AC-10: conversation ID only; no tenant/user in the common area."""
    list_text = client.get("/api/analysis/conversations").text
    detail_text = client.get(f"/api/analysis/conversations/{POSITIVE_ID}").text
    for blob in (list_text, detail_text):
        lowered = blob.lower()
        assert "tenant" not in lowered
        assert "20256789" not in blob  # the fixtures' tenant id must not leak


def test_list_filters_by_category():
    res = client.get("/api/analysis/conversations", params={"category": "positive_feedback"})
    assert res.status_code == 200
    for item in res.json()["items"]:
        assert item["category"] == "positive_feedback"


def test_list_bulk_loads_conversations(monkeypatch):
    records = main_module.store.list()
    conversations = {
        record.conversation_id: main_module.store.get_conversation(record.conversation_id)
        for record in records
    }
    calls = []
    monkeypatch.setattr(
        main_module.store,
        "get_conversations",
        lambda ids: calls.append(ids) or {cid: conversations[cid] for cid in ids},
        raising=False,
    )
    monkeypatch.setattr(
        main_module.store,
        "get_conversation",
        lambda _conversation_id: (_ for _ in ()).throw(AssertionError("single-row lookup used")),
    )

    assert client.get("/api/analysis/conversations").status_code == 200
    assert len(calls) == 1


def test_list_paginates_and_searches_on_the_server():
    first = client.get("/api/analysis/conversations", params={"limit": 2, "offset": 0}).json()
    second = client.get("/api/analysis/conversations", params={"limit": 2, "offset": 2}).json()
    assert len(first["items"]) == 2
    assert first["total"] >= 4
    assert {item["conversation_id"] for item in first["items"]}.isdisjoint(
        item["conversation_id"] for item in second["items"]
    )
    conversation_id = first["items"][0]["conversation_id"]
    searched = client.get("/api/analysis/conversations", params={"query": conversation_id}).json()
    assert searched["total"] == 1
    assert searched["items"][0]["conversation_id"] == conversation_id


def test_list_filters_missing_telemetry():
    body = client.get(
        "/api/analysis/conversations", params={"review_state": "missing_telemetry"}
    ).json()
    assert body["items"]
    assert all(
        item["metrics"]["ttft_ms"] is None
        or item["metrics"]["input_tokens"] is None
        or item["metrics"]["output_tokens"] is None
        for item in body["items"]
    )


def test_list_rejects_unknown_category_with_problem():
    res = client.get("/api/analysis/conversations", params={"category": "bogus"})
    assert res.status_code == 400
    assert res.headers["content-type"].startswith("application/problem+json")


def test_detail_has_analysis_messages_feedback_and_metrics():
    res = client.get(f"/api/analysis/conversations/{POSITIVE_ID}")
    assert res.status_code == 200
    body = res.json()
    assert body["analysis"]["category"] == "positive_feedback"
    assert body["messages"] and body["messages"][0]["sequence_num"] == 1
    assert set(body["metrics"]) == {"ttft_ms", "input_tokens", "output_tokens", "prompt_tokens"}


def test_missing_telemetry_is_null_not_zero():
    """AC-7: missing latency/token telemetry shown as unavailable (null), not zero."""
    res = client.get(f"/api/analysis/conversations/{NON_ENGLISH_MISSING_TELEMETRY_ID}")
    metrics = res.json()["metrics"]
    assert metrics["ttft_ms"] is None
    assert metrics["input_tokens"] is None


def test_non_english_conversation_is_categorised():
    """AC-8: a non-English conversation still receives a category."""
    res = client.get(f"/api/analysis/conversations/{NON_ENGLISH_MISSING_TELEMETRY_ID}")
    assert res.json()["analysis"]["category"] in CATEGORIES


def test_human_override_updates_effective_category_and_audits():
    res = client.post(
        f"/api/analysis/conversations/{POSITIVE_ID}/override",
        json={"category": "out_of_scope", "actor": "reviewer@jaggaer.com"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["category"] == "out_of_scope"  # effective
    assert body["model_category"] == "positive_feedback"  # original retained (audit)
    assert body["override"]["actor"] == "reviewer@jaggaer.com"
    # reflected in the detail record
    detail = client.get(f"/api/analysis/conversations/{POSITIVE_ID}").json()
    assert detail["analysis"]["category"] == "out_of_scope"
    assert detail["analysis"]["model_category"] == "positive_feedback"


def test_override_rejects_unknown_category():
    res = client.post(
        f"/api/analysis/conversations/{POSITIVE_ID}/override",
        json={"category": "nope", "actor": "x"},
    )
    assert res.status_code == 400


def test_latest_run_summary_exposes_counts():
    res = client.get("/api/analysis/runs/latest")
    assert res.status_code == 200
    body = res.json()
    assert "analysed" in body and "unanalysed" in body


def test_queue_summary_exposes_live_items():
    res = client.get("/api/analysis/queue")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {
        "queued", "in_flight", "in_flight_or_queued", "dead_letter",
        "capacity", "workers", "started", "items", "limit", "offset",
    }


def test_user_conversations_endpoint_paginates(monkeypatch):
    monkeypatch.setattr(
        "app.dashboard.user_conversations",
        lambda store, tenant_id, user_id, limit, offset, region=None: ([], 42),
    )
    body = client.get(
        "/api/analysis/dashboard/tenants/t1/users/u1/conversations",
        params={"limit": 10, "offset": 20},
    ).json()
    assert body == {"items": [], "total": 42, "limit": 10, "offset": 20}


def test_openapi_is_3_1():
    assert app.openapi()["openapi"].startswith("3.1")
