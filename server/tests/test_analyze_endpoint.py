"""On-demand analyse endpoint: the daily rate-limit gate returns 429."""

from fastapi.testclient import TestClient

from app.main import app, store


def test_on_demand_analyze_is_rate_limited(monkeypatch):
    # Pretend this conversation already hit today's cap → gate before any chat-DB call.
    monkeypatch.setattr(store, "analyses_today", lambda cid, today=None: 99)
    res = TestClient(app).post("/api/analysis/conversations/abc123/analyze")
    assert res.status_code == 429
