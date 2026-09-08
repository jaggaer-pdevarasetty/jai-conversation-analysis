"""Persistent SQL store against PostgreSQL (ADR-0009). No SQLite.

Runs against TEST_DATABASE_URL (default: the local podman/Docker Postgres). Skips cleanly
if no Postgres is reachable (e.g. CI without a Postgres service).
"""

import os
from dataclasses import asdict

import pytest
from sqlalchemy import create_engine, text

from app.deidentify import deidentify
from app.domain.analyze import analyze
from app.fixtures import CONVERSATIONS
from app.store_sql import SqlResultStore, _row_to_rec

# Opt-in only: set TEST_DATABASE_URL to a DISPOSABLE Postgres. If unset, these tests SKIP —
# so pytest/pre-commit can never truncate the app's real `analysis` DB.
PG_URL = os.getenv("TEST_DATABASE_URL")
POSITIVE = next(c for c in CONVERSATIONS if c.feedback.rating is True)


@pytest.fixture
def store() -> SqlResultStore:
    if not PG_URL:
        pytest.skip("set TEST_DATABASE_URL (a disposable DB) to run SQL-store tests")
    try:
        s = SqlResultStore(PG_URL)  # create_all connects → raises if unreachable
    except Exception as exc:  # noqa: BLE001 - report why we skipped
        pytest.skip(f"Postgres not reachable at TEST_DATABASE_URL: {type(exc).__name__}")
    engine = create_engine(PG_URL)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE analysis, conversation, failed, override_event"))
    engine.dispose()
    return s


def test_legacy_analysis_fields_are_ignored():
    record = analyze(POSITIVE, "run")
    data = asdict(record) | {"enrichment": {"legacy": True}}
    assert _row_to_rec(data).conversation_id == record.conversation_id


def test_persists_and_reads_back(store: SqlResultStore):
    store.upsert(analyze(POSITIVE, "run"), deidentify(POSITIVE))
    got = store.get_analysis(POSITIVE.id)
    assert got is not None and got.category == "positive_feedback"
    assert store.get_conversation(POSITIVE.id).conversation_id == POSITIVE.id
    assert store.count_by_category()["positive_feedback"] == 1
    # survives a fresh connection to the same database (real persistence)
    assert SqlResultStore(PG_URL).get_analysis(POSITIVE.id) is not None


def test_override_is_persisted(store: SqlResultStore):
    store.upsert(analyze(POSITIVE, "run"), deidentify(POSITIVE))
    store.set_override(POSITIVE.id, "out_of_scope", "reviewer@jaggaer.com")
    rec = SqlResultStore(PG_URL).get_analysis(POSITIVE.id)
    assert rec.category == "out_of_scope"  # effective (override)
    assert rec.model_category == "positive_feedback"  # original retained (audit)


def test_override_audit_trail_is_persisted_append_only(store: SqlResultStore):
    """Auditability NFR: every override event lands in the append-only override_event table
    and survives a fresh connection — not just the latest override on the record. Each entry
    carries its previous category (self-contained old→new transition)."""
    record = analyze(POSITIVE, "run")
    store.upsert(record, deidentify(POSITIVE))
    store.set_override(POSITIVE.id, "out_of_scope", "reviewer-a")
    store.set_override(POSITIVE.id, "failed_to_resolve", "reviewer-b")
    fresh = SqlResultStore(PG_URL)  # new connection → real persistence, oldest first
    events = fresh.override_events(POSITIVE.id)
    assert [(e.category, e.actor) for e in events] == [
        ("out_of_scope", "reviewer-a"),
        ("failed_to_resolve", "reviewer-b"),
    ]
    assert events[0].previous_category == record.model_category  # transition starts at the model label
    assert events[1].previous_category == "out_of_scope"
    assert fresh.override_events("never-overridden") == []


def test_failed_count_is_visible_and_region_scoped(store: SqlResultStore):
    store.mark_failed("unanalysed-id", region="us")
    store.mark_failed("other-id", region="eu")
    store.mark_failed("unknown-region-id")  # batch-level failure — region unknown
    assert store.unanalysed_count() == 3  # env-wide
    assert store.unanalysed_count(region="us") == 1
    assert store.unanalysed_count(region="eu") == 1
    assert store.unanalysed_count(region="uk") == 0  # unknown-region rows excluded per-region
