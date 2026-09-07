"""Eval harness — validated against the deterministic rules baseline (no network)."""

import json

from app.domain.analyze import analyze
from app.domain.models import CATEGORIES
from app.eval import GOLD, GOLD_FILE, evaluate, load_gold


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


def test_gold_file_loads_and_covers_every_category():
    """The version-controlled gold set (server/eval_gold.json) is valid, covers all five
    categories, and is what the harness measures against (grow it to 100-200 for the real
    >=85% measurement — reviewers add labelled conversations without code changes)."""
    assert GOLD_FILE.exists(), "eval_gold.json must stay committed next to the server package"
    gold = load_gold()
    assert len(gold) >= 6
    assert set(gold.values()) == set(CATEGORIES)
    assert all(gold.get(cid) == cat for cid, cat in GOLD.items())  # seed entries always present


def test_gold_file_rejects_invalid_entries_loudly(tmp_path, monkeypatch):
    """A malformed gold entry fails the load loudly — never a silently wrong measurement."""
    bad = tmp_path / "eval_gold.json"
    bad.write_text(json.dumps([{"conversation_id": "x", "category": "not-a-category"}]))
    monkeypatch.setattr("app.eval.GOLD_FILE", bad)
    try:
        load_gold()
        raise AssertionError("invalid gold entries must raise")
    except ValueError as exc:
        assert "not-a-category" in str(exc)
