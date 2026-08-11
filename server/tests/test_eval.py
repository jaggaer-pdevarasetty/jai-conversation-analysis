"""Eval harness — validated against the deterministic rules baseline (no network)."""

from app.domain.analyze import analyze
from app.eval import evaluate


def test_rules_baseline_meets_threshold_and_has_no_critical_failures():
    report = evaluate(analyze)
    assert report.total == 6
    assert report.agreement >= 0.85  # rules agree with the gold set on the fixtures
    assert report.critical_failures == []
    assert report.passed()


def test_harness_flags_resolved_mislabel_as_critical():
    """A classifier that always says 'resolved' must FAIL the hard gate (AC-quality)."""

    def always_resolved(conv, run_id, now):
        rec = analyze(conv, run_id, now)
        rec.model_category = "resolved"
        rec.override = None
        return rec

    report = evaluate(always_resolved)
    assert report.critical_failures  # failed_to_resolve / out_of_scope → resolved caught
    assert not report.passed()


def test_confusion_matrix_is_populated():
    report = evaluate(analyze)
    assert sum(report.confusion.values()) == report.total
