"""Persistent SQL store against PostgreSQL (ADR-0009). No SQLite.

Runs against TEST_DATABASE_URL (default: the local podman/Docker Postgres). Skips cleanly
if no Postgres is reachable (e.g. CI without a Postgres service).
"""

import os

import pytest
from sqlalchemy import create_engine, text

from app.deidentify import deidentify
from app.domain.analyze import analyze
from app.fixtures import CONVERSATIONS
from app.store_sql import SqlResultStore

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
        conn.execute(text("TRUNCATE analysis, conversation, failed"))
    engine.dispose()
    return s


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


def test_failed_count_is_visible(store: SqlResultStore):
    store.mark_failed("unanalysed-id")
    assert store.unanalysed_count() == 1
