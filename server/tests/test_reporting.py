"""Reporting + operational metrics over analysed fixtures."""

from datetime import datetime, timezone

from app.fixtures import CONVERSATIONS
from app.reporting import operational_stats, product_report
from app.run import run_analysis
from app.store import CommonStore


def _seeded_store() -> CommonStore:
    store = CommonStore()
    run_analysis(store, CONVERSATIONS, now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    return store


def test_operational_stats_reports_totals_and_analyzers():
    store = _seeded_store()
    s = operational_stats(store)
    assert s["analysed"] == len(CONVERSATIONS)
    assert set(s["counts"]) == {
        "resolved", "failed_to_resolve", "positive_feedback", "negative_feedback", "out_of_scope",
    }
    assert "tokens" in s and "analyzers" in s


def test_product_report_has_distribution_and_use_cases():
    store = _seeded_store()
    r = product_report(store)
    assert r["total_analysed"] == len(CONVERSATIONS)
    # percentages across categories sum to ~100
    assert abs(sum(v["pct"] for v in r["category_distribution"].values()) - 100.0) < 1.0
    assert "top_issues" in r and "new_use_cases" in r
    assert isinstance(r["new_use_cases"], list)  # out-of-scope requests (may be empty)
