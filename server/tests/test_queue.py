"""AnalysisQueue: dedup (no re-run/loop), processing, and dead-letter — no network."""

import time

from app.domain.analyze import analyze
from app.fixtures import CONVERSATIONS
from app.queue import AnalysisQueue
from app.store import CommonStore

IDS = [c.id for c in CONVERSATIONS]


def _rules_batch(convs, run_id, now):
    return [analyze(c, run_id, now) for c in convs]


def _wait(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        time.sleep(0.05)
    return cond()


def test_enqueue_dedupes_and_skips_already_analysed(monkeypatch):
    store = CommonStore()
    q = AnalysisQueue(store, _rules_batch, workers=0)  # no workers → inspect queue only
    # patch chatdb load used by the worker (not needed here since workers=0)
    accepted1 = q.enqueue(IDS)
    accepted2 = q.enqueue(IDS)  # same ids again → all deduped
    assert set(accepted1) == set(IDS)
    assert accepted2 == []  # no re-enqueue → cannot loop
    stats = q.stats()
    assert stats["queued"] == len(IDS)
    assert stats["in_flight"] == 0
    assert {item["conversation_id"] for item in stats["items"]} == set(IDS)
    assert all(item["status"] == "queued" for item in stats["items"])


def test_stats_are_scoped_by_environment():
    store = CommonStore()
    q = AnalysisQueue(store, _rules_batch, workers=0)  # no workers → inspect queue only
    q.enqueue(IDS[:2], env="uit")
    q.enqueue(IDS[2:4], env="prod")

    uit = q.stats(env="uit")
    prod = q.stats(env="prod")
    assert uit["in_flight_or_queued"] == 2
    assert prod["in_flight_or_queued"] == 2
    assert {i["conversation_id"] for i in uit["items"]} == set(IDS[:2])
    assert {i["conversation_id"] for i in prod["items"]} == set(IDS[2:4])
    assert all(i["environment"] == "uit" for i in uit["items"])
    assert all(i["environment"] == "prod" for i in prod["items"])
    # the unscoped view still sees everything (admin/debug)
    assert q.stats()["in_flight_or_queued"] == 4


def test_worker_processes_then_never_reruns(monkeypatch):
    store = CommonStore()
    # the worker loads conversations from chatdb by id; stub it with our fixtures
    import app.queue as qmod

    monkeypatch.setattr(
        "app.chatdb.load_from_chatdb",
        lambda ids=None, **kw: [c for c in CONVERSATIONS if c.id in set(ids or [])],
    )
    q = AnalysisQueue(store, _rules_batch, workers=1, batch_size=3)
    q.start()
    q.enqueue(IDS)
    assert _wait(lambda: all(store.is_analysed(i) for i in IDS)), "all should get analysed"
    # re-enqueue analysed ids → skipped (idempotent, no loop)
    assert q.enqueue(IDS) == []
    assert store.unanalysed_count() == 0
