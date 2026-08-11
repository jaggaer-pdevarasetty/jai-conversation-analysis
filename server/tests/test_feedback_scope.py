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
