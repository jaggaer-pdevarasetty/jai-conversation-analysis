"""Manual analysis trigger (POST /analyze/sweep) replaces the scheduled sweep."""

import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app

client = TestClient(app)


def test_manual_sweep_is_chatdb_only():
    # tests run on the fixtures source → the manual chat-DB sweep is not applicable
    r = client.post("/api/analysis/analyze/sweep")
    assert r.status_code == 400
    assert r.json()["title"] == "Not available"


def test_analyze_pending_returns_a_count():
    # step 1 of the flow: fetch (don't analyse) — safe on the fixtures source (count 0)
    r = client.get("/api/analysis/analyze/pending")
    assert r.status_code == 200
    body = r.json()
    assert "count" in body and body["count"] == 0


def test_analyze_pending_returns_every_conversation(monkeypatch):
    ids = [f"c{index}" for index in range(16)]
    monkeypatch.setattr(main_module, "settings", SimpleNamespace(source="chatdb"))
    monkeypatch.setattr(main_module.store, "analysed_ids", lambda env="uit": set())
    monkeypatch.setattr(main_module, "_eligible_by_region", lambda region=None, env="uit", feedback_only=False: {"us": ids})
    monkeypatch.setattr(
        "app.dashboard.conversation_meta",
        lambda conversation_ids, region=None, env="uit": {
            cid: {"region": "us", "title": cid, "tenant_name": "Tenant", "last_message_at": None}
            for cid in conversation_ids
        },
    )
    body = main_module.analyze_pending(region=None)
    assert body["count"] == 16
    assert len(body["ids"]) == 16
    assert len(body["items"]) == 16


def test_trigger_sweep_runs_once_and_dedupes(monkeypatch):
    monkeypatch.setattr(main_module, "_sweeps_running", set(), raising=False)
    started, release, calls = threading.Event(), threading.Event(), []

    def fake_sweep(region=None, env="uit", feedback_only=False):
        calls.append(region)
        started.set()
        release.wait(timeout=2)

    monkeypatch.setattr(main_module, "_sweep", fake_sweep)
    assert main_module.trigger_sweep() is True        # kicks off a background UIT sweep
    assert started.wait(timeout=2)
    assert main_module.trigger_sweep() is False       # same env already running → deduped
    assert main_module.trigger_sweep(env="prod") is True  # other env is independent → not blocked
    release.set()


def test_analyze_rejects_empty_conversation(monkeypatch):
    # A conversation with no messages must NOT be analysed (would produce a hallucinated label).
    from app.domain.models import Conversation, Feedback

    empty = Conversation(id="x1", tenant_id="t", title=None, created_at="", messages=[], feedback=Feedback())
    monkeypatch.setattr("app.chatdb.load_one_from_chatdb", lambda cid, env="uit": empty)
    r = client.post("/api/analysis/conversations/x1/analyze")
    assert r.status_code == 422
    assert r.json()["title"] == "No transcript"


def test_no_scheduler_running():
    # We moved to a manual trigger — there must be no periodic scheduler wired up.
    assert not hasattr(main_module, "scheduler") or main_module.scheduler is None
