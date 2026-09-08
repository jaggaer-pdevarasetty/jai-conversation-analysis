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


def test_gold_entries_without_conversations_fail_unless_allowed():
    """A gold entry that can't be evaluated is a FAILED measurement, never a silent skip:
    it is recorded as missing and fails the gate unless explicitly allowed (CI, no store)."""
    gold = {**GOLD, "not-loaded-anywhere": "resolved"}
    report = evaluate(analyze, gold=gold)
    assert report.missing == ["not-loaded-anywhere"]
    assert report.total == len(GOLD)  # only the evaluable entries are scored
    assert not report.passed()  # incomplete coverage → FAIL

    allowed = evaluate(analyze, gold=gold, allow_missing=True)
    assert allowed.missing == ["not-loaded-anywhere"]  # still surfaced…
    assert allowed.passed()  # …but permitted (CI mode: no results store to load from)


def test_real_gold_conversations_are_loaded_from_the_results_store(monkeypatch):
    """Growing eval_gold.json with REAL conversation ids must actually evaluate them: they are
    loaded from our own results store (de-identified transcripts) and classified like production."""
    from dataclasses import replace

    from app.config import settings
    from app.deidentify import deidentify
    from app.domain.analyze import analyze as rules
    from app.eval import load_eval_conversations
    from app.fixtures import CONVERSATIONS
    from app.store import CommonStore

    real = replace(CONVERSATIONS[0], id="real-gold-conv-1")  # a stand-in for a stored conversation
    store = CommonStore()
    store.upsert(rules(real, "run"), deidentify(real))
    # Settings is a frozen dataclass → patch the module attribute with a replaced instance
    # (eval.py imports `settings` at call time, so it picks this up).
    monkeypatch.setattr("app.config.settings", replace(settings, store_backend="sql"))
    monkeypatch.setattr("app.store_factory.make_store", lambda: store)

    gold = {"real-gold-conv-1": "resolved"}
    convs = {c.id: c for c in load_eval_conversations(gold)}
    assert "real-gold-conv-1" in convs  # sourced from the store, not just the fixtures
    report = evaluate(analyze, conversations=list(convs.values()), gold=gold)
    assert report.total == 1 and report.missing == []
    assert report.passed()


def test_model_outage_cannot_pass_the_quality_gate(monkeypatch, capsys):
    """When Vertex is configured but produces no record, the eval must FAIL even though the
    rules fallback would agree — an unavailable model is an outage, not a passing measurement."""
    from dataclasses import replace

    from app import gemini
    from app.config import settings
    from app.eval import main

    # Settings is frozen → swap in a replaced instance (vertex_configured becomes True).
    monkeypatch.setattr(
        "app.config.settings",
        replace(settings, vertex_project="proj", vertex_location="us-central1"),
    )
    monkeypatch.setattr(gemini, "make_batch_analyzer", lambda: (lambda convs, run_id, now: []))

    assert main([]) == 1  # gate FAILS on the rules fallback while the model is down
    out = capsys.readouterr().out
    assert "MODEL UNAVAILABLE" in out


def test_eval_cli_passes_on_the_rules_baseline(monkeypatch, capsys):
    """Without Vertex configured the gate measures the deterministic rules baseline (CI mode)."""
    from app.eval import main

    assert main(["--allow-missing"]) == 0
    out = capsys.readouterr().out
    assert "RESULT: PASS" in out
    assert f"evaluable: {len(load_gold())}/{len(load_gold())}" in out
