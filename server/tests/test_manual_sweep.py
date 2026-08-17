"""Manual analysis trigger (POST /analyze/sweep) replaces the scheduled sweep."""

import threading

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


def test_trigger_sweep_runs_once_and_dedupes(monkeypatch):
    monkeypatch.setattr(main_module, "_sweep_running", False, raising=False)
    started, release, calls = threading.Event(), threading.Event(), []

    def fake_sweep():
        calls.append(1)
        started.set()
        release.wait(timeout=2)

    monkeypatch.setattr(main_module, "_sweep", fake_sweep)
    assert main_module.trigger_sweep() is True        # kicks off a background sweep
    assert started.wait(timeout=2)
    assert main_module.trigger_sweep() is False       # already running → deduped, no pile-up
    release.set()
    assert calls == [1]


def test_no_scheduler_running():
    # We moved to a manual trigger — there must be no periodic scheduler wired up.
    assert not hasattr(main_module, "scheduler") or main_module.scheduler is None
