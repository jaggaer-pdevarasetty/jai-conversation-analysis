"""In-memory store: on-demand analyse rate-limit bookkeeping + override audit trail."""

from app.deidentify import deidentify
from app.domain.analyze import analyze
from app.domain.models import Override
from app.fixtures import CONVERSATIONS
from app.store import CommonStore


def test_analyses_today_counts_only_todays_events():
    store = CommonStore()
    store.record_analysis("c1", "2026-08-11T09:00:00+00:00")
    store.record_analysis("c1", "2026-08-11T10:00:00+00:00")
    store.record_analysis("c1", "2026-08-10T10:00:00+00:00")  # yesterday
    assert store.analyses_today("c1", today="2026-08-11") == 2
    assert store.analyses_today("c1", today="2026-08-10") == 1
    assert store.analyses_today("unknown", today="2026-08-11") == 0


def test_override_history_is_append_only_and_ordered():
    """Auditability (J1-93353): EVERY override is retained, oldest first — not just the latest."""
    store = CommonStore()
    conv = CONVERSATIONS[0]
    store.upsert(analyze(conv, "run"), deidentify(conv))
    store.set_override(conv.id, "out_of_scope", "reviewer-a")
    store.set_override(conv.id, "failed_to_resolve", "reviewer-b")
    store.set_override(conv.id, "negative_feedback", "reviewer-a")

    events = store.override_events(conv.id)
    assert [e.category for e in events] == ["out_of_scope", "failed_to_resolve", "negative_feedback"]
    assert [e.actor for e in events] == ["reviewer-a", "reviewer-b", "reviewer-a"]
    # ascending timestamps, latest matches the effective override on the record
    assert [e.at for e in events] == sorted(e.at for e in events)
    record = store.get_analysis(conv.id)
    assert record is not None and isinstance(record.override, Override)
    assert record.override.category == "negative_feedback" == events[-1].category
    # history is per-conversation
    assert store.override_events("unknown-id") == []


def test_override_history_is_isolated_per_environment():
    store = CommonStore()
    conv = CONVERSATIONS[0]
    rec = analyze(conv, "run")
    rec_env = analyze(conv, "run")
    store.upsert(rec, deidentify(conv))
    rec_env.environment = "prod"
    store.upsert(rec_env, deidentify(conv))
    store.set_override(conv.id, "out_of_scope", "reviewer-a", env="uit")
    store.set_override(conv.id, "resolved", "reviewer-b", env="prod")
    assert [e.category for e in store.override_events(conv.id, env="uit")] == ["out_of_scope"]
    assert [e.category for e in store.override_events(conv.id, env="prod")] == ["resolved"]

