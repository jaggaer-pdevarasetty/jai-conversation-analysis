"""Persistent SQL store (SQLite here; same code path runs on Postgres). ADR-0009."""

from app.deidentify import deidentify
from app.domain.analyze import analyze
from app.fixtures import CONVERSATIONS
from app.store_sql import SqlResultStore

POSITIVE = next(c for c in CONVERSATIONS if c.feedback.rating is True)


def test_persists_and_reads_back(tmp_path):
    url = f"sqlite:///{tmp_path}/analysis.db"
    store = SqlResultStore(url)
    store.upsert(analyze(POSITIVE, "run"), deidentify(POSITIVE))

    got = store.get_analysis(POSITIVE.id)
    assert got is not None and got.category == "positive_feedback"
    assert store.get_conversation(POSITIVE.id).conversation_id == POSITIVE.id
    assert store.count_by_category()["positive_feedback"] >= 1

    # survives a fresh connection to the same database file (real persistence)
    reopened = SqlResultStore(url)
    assert reopened.get_analysis(POSITIVE.id) is not None


def test_override_is_persisted(tmp_path):
    store = SqlResultStore(f"sqlite:///{tmp_path}/analysis.db")
    store.upsert(analyze(POSITIVE, "run"), deidentify(POSITIVE))
    store.set_override(POSITIVE.id, "out_of_scope", "reviewer@jaggaer.com")
    rec = store.get_analysis(POSITIVE.id)
    assert rec.category == "out_of_scope"  # effective (override)
    assert rec.model_category == "positive_feedback"  # original retained (audit)


def test_failed_count_is_visible(tmp_path):
    store = SqlResultStore(f"sqlite:///{tmp_path}/analysis.db")
    store.mark_failed("unanalysed-id")
    assert store.unanalysed_count() == 1
