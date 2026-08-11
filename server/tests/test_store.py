"""In-memory store: on-demand analyse rate-limit bookkeeping."""

from app.store import CommonStore


def test_analyses_today_counts_only_todays_events():
    store = CommonStore()
    store.record_analysis("c1", "2026-08-11T09:00:00+00:00")
    store.record_analysis("c1", "2026-08-11T10:00:00+00:00")
    store.record_analysis("c1", "2026-08-10T10:00:00+00:00")  # yesterday
    assert store.analyses_today("c1", today="2026-08-11") == 2
    assert store.analyses_today("c1", today="2026-08-10") == 1
    assert store.analyses_today("unknown", today="2026-08-11") == 0
