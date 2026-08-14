"""/feedback scope: thumbs (default) vs outcomes vs all + validation."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_feedback_scopes_are_supported():
    for scope in ("thumbs", "outcomes", "all"):
        res = client.get(f"/api/analysis/feedback?scope={scope}")
        assert res.status_code == 200
        body = res.json()
        assert body["scope"] == scope
        assert {"total", "positive", "negative", "negative_outcomes"} <= set(body)


def test_feedback_default_scope_is_thumbs():
    assert client.get("/api/analysis/feedback").json()["scope"] == "thumbs"


def test_feedback_rejects_unknown_scope():
    assert client.get("/api/analysis/feedback?scope=bogus").status_code == 422


def test_feedback_filters_and_paginates_on_the_server():
    first = client.get(
        "/api/analysis/feedback",
        params={"rating": "positive", "sort": "newest", "limit": 1, "offset": 0},
    ).json()
    assert len(first["items"]) <= 1
    assert all(item["rating"] is True for item in first["items"])
    assert first["limit"] == 1 and first["offset"] == 0
    assert first["scope_total"] >= first["total"]
    assert "deep_analysed" in first


def test_feedback_defaults_to_latest_conversation_activity():
    body = client.get("/api/analysis/feedback", params={"limit": 100}).json()
    dates = [item["last_message_at"] or item["analyzed_at"] for item in body["items"]]
    assert dates == sorted(dates, reverse=True)


def test_feedback_searches_by_conversation_id():
    item = client.get("/api/analysis/feedback", params={"limit": 1}).json()["items"][0]
    result = client.get(
        "/api/analysis/feedback",
        params={"query": item["conversation_id"], "limit": 1},
    ).json()
    assert result["total"] == 1
    assert result["items"][0]["conversation_id"] == item["conversation_id"]
