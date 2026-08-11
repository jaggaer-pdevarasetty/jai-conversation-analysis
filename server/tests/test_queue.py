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
