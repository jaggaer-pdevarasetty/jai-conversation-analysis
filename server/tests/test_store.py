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
    """Auditability (J1-93353): EVERY override is retained, oldest first — not just the latest.
    Each entry is a self-contained old→new transition (previous_category)."""
    store = CommonStore()
    conv = CONVERSATIONS[0]
    record = analyze(conv, "run")
    store.upsert(record, deidentify(conv))
    store.set_override(conv.id, "out_of_scope", "reviewer-a")
    store.set_override(conv.id, "failed_to_resolve", "reviewer-b")
    store.set_override(conv.id, "negative_feedback", "reviewer-a")

    events = store.override_events(conv.id)
    assert [e.category for e in events] == ["out_of_scope", "failed_to_resolve", "negative_feedback"]
    assert [e.actor for e in events] == ["reviewer-a", "reviewer-b", "reviewer-a"]
    # first transition starts from the model label; each later one from the prior override
    assert events[0].previous_category == record.model_category
    for earlier, later in zip(events, events[1:]):
        assert later.previous_category == earlier.category
    # ascending timestamps, latest matches the effective override on the record
    assert [e.at for e in events] == sorted(e.at for e in events)
    current = store.get_analysis(conv.id)
    assert current is not None and isinstance(current.override, Override)
    assert current.override.category == "negative_feedback" == events[-1].category
    assert current.override.previous_category == events[-2].category
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


def test_unanalysed_count_is_region_scoped():
    """Regional dashboards must not see other regions' failures: the count is env-wide only
    when no region is given; unknown-region ("") failures never land in a region's count."""
    store = CommonStore()
    store.mark_failed("c-us", region="us")
    store.mark_failed("c-eu", region="eu")
    store.mark_failed("c-unknown")  # batch-level failure — region not known
    assert store.unanalysed_count() == 3  # env-wide sees everything
    assert store.unanalysed_count(region="us") == 1
    assert store.unanalysed_count(region="eu") == 1
    assert store.unanalysed_count(region="uk") == 0  # unknown-region rows excluded per-region
    # analysis success clears the failed entry regardless of region
    from dataclasses import replace

    conv = replace(CONVERSATIONS[0], id="c-us")
    store.upsert(analyze(conv, "run"), deidentify(conv))
    assert store.unanalysed_count() == 2
    assert store.unanalysed_count(region="us") == 0

