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
    monkeypatch.setattr(main_module, "settings", SimpleNamespace(source="chatdb", analysis_lookback_days=lambda env: 15 if env == "prod" else None))
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


def test_analyze_pending_preview_uses_newest_across_regions(monkeypatch):
    us_ids = [f"us-{index}" for index in range(51)]
    eu_ids = ["eu-newest"]
    monkeypatch.setattr(main_module, "settings", SimpleNamespace(source="chatdb", analysis_lookback_days=lambda env: 15 if env == "prod" else None))
    monkeypatch.setattr(main_module.store, "analysed_ids", lambda env="uit": set())
    monkeypatch.setattr(main_module.analysis_queue, "in_progress_ids", lambda env: set())
    monkeypatch.setattr(main_module.analysis_queue, "dead_ids", lambda env: set())
    monkeypatch.setattr(
        main_module,
        "_eligible_by_region",
        lambda region=None, env="uit", feedback_only=False: {"us": us_ids, "eu": eu_ids},
    )

    def meta(conversation_ids, region=None, env="uit"):
        return {
            cid: {
                "region": "eu" if cid.startswith("eu") else "us",
                "title": cid,
                "tenant_name": "Tenant",
                "last_message_at": "2026-09-19T04:30:00+00:00" if cid.startswith("eu") else "2026-09-18T04:30:00+00:00",
            }
            for cid in conversation_ids
        }

    monkeypatch.setattr("app.dashboard.conversation_meta", meta)
    body = main_module.analyze_pending(region=None)

    assert body["count"] == 52
    assert len(body["items"]) == 50
    assert body["items"][0]["conversation_id"] == "eu-newest"


def test_pending_feedback_summary_counts_negative_messages(monkeypatch):
    from app.domain.models import Conversation, Enrichment, Feedback, Message

    conv = Conversation(
        id="c1",
        tenant_id="t",
        title="Deep research issue",
        created_at="2026-10-01T10:00:00+00:00",
        region="us",
        messages=[
            Message(id="m1", role="assistant", content="a", sequence_num=1, created_at="2026-10-01T10:01:00+00:00"),
            Message(id="m2", role="assistant", content="b", sequence_num=2, created_at="2026-10-01T10:02:00+00:00"),
            Message(id="m3", role="assistant", content="c", sequence_num=3, created_at="2026-10-01T10:03:00+00:00"),
        ],
        feedback=Feedback(rating=False, comment="wrong", message_id="m1"),
        feedbacks=[
            Feedback(rating=False, comment="wrong", message_id="m1"),
            Feedback(rating=False, comment="still wrong", message_id="m2"),
            Feedback(rating=True, comment="fixed", message_id="m3"),
        ],
    )
    calls = []

    def load(ids, env="uit"):
        calls.append(("load", env))
        return [conv]

    def enrich(_cid, _region, env="uit", with_prompt=False):
        calls.append(("enrich", env))
        return Enrichment(
            platform="JI",
            agent_used="deep-research",
            interaction_mode="Deep Research",
            frustration_score=0.84,
            langsmith_found=True,
        )

    def meta(ids, region=None, env="uit"):
        calls.append(("meta", env))
        return {"c1": {"tenant_name": "Tenant One", "title": "Deep research issue"}}

    monkeypatch.setattr("app.chatdb.load_from_chatdb", load)
    monkeypatch.setattr("app.enrichment.fetch_enrichment", enrich)
    monkeypatch.setattr("app.dashboard.conversation_meta", meta)

    out = main_module._pending_feedback_summary({"us": ["c1"]}, "prod")

    assert out["negative_feedback_messages"] == 2
    assert out["negative_by_region"] == {"us": 2}
    assert out["negative_by_mode"] == {"Deep Research": 2}
    assert out["deep_research_negative"] == 2
    assert out["average_frustration"] == 0.84
    assert len(out["negative_items"]) == 2
    assert all(item["platform"] == "JI" for item in out["negative_items"])
    assert calls == [("load", "prod"), ("enrich", "prod"), ("meta", "prod")]


def test_prod_eligible_scan_receives_fifteen_day_lookback(monkeypatch):
    from app.config import RegionConfig

    calls = []
    region = RegionConfig("us", "postgresql://example", "chat", "public")
    monkeypatch.setattr(main_module, "settings", SimpleNamespace(analysis_lookback_days=lambda env: 15 if env == "prod" else None))
    monkeypatch.setattr("app.chatdb.configured_regions", lambda env="uit": [region])
    monkeypatch.setattr(
        "app.chatdb._eligible_in_region",
        lambda _region, _engine, _limit, feedback_only=False, lookback_days=None: calls.append(
            (feedback_only, lookback_days)
        ) or ["recent"],
    )

    assert main_module._eligible_by_region(env="prod", feedback_only=True) == {"us": ["recent"]}
    assert calls == [(True, 15)]


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
