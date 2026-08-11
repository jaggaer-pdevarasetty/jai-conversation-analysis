"""In-process analysis queue — bounded, deduped, worker-pooled, with retry + dead-letter.

Why this exists: FastAPI BackgroundTasks is not a real queue (no bound, no dedup, no retry,
lost on restart). This gives predictable behaviour at load and, crucially, **never re-runs or
loops**:

- **No loop / no re-run:** an id already analysed (`store.is_analysed`) is skipped; an id
  already queued or in-flight is not enqueued again (dedup set); a permanently failing id is
  moved to a dead-letter after `max_attempts` and never retried again.
- **Bounded:** a fixed `maxsize`; when full, `enqueue` applies backpressure (skips the rest)
  rather than exploding memory.
- **Concurrency:** a small fixed worker pool pulls items and analyses them in batches.

At multi-instance scale, swap the internal `queue.Queue` for Redis / Cloud Tasks / PubSub —
the `enqueue()` contract and worker loop stay the same.
"""

from __future__ import annotations

import queue
import threading
import time
from datetime import datetime, timezone

from .config import settings


class AnalysisQueue:
    def __init__(
        self,
        store,
        analyze_batch,
        *,
        workers: int = 2,
        maxsize: int = 5000,
        batch_size: int | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._store = store
        self._analyze = analyze_batch  # (convs, run_id, now_iso) -> [AnalysisRecord]
        self._q: queue.Queue[str] = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._queued: set[str] = set()  # in queue OR in-flight (dedup)
        self._in_flight: set[str] = set()
        self._retrying: set[str] = set()
        self._queued_at: dict[str, str] = {}
        self._attempts: dict[str, int] = {}
        self._dead: set[str] = set()
        self._batch_size = batch_size or settings.batch_size
        self._max_attempts = max_attempts
        self._workers = [threading.Thread(target=self._work, name=f"analyzer-{i}", daemon=True) for i in range(workers)]
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._started = True
            for w in self._workers:
                w.start()

    def enqueue(self, conversation_ids: list[str]) -> list[str]:
        """Add ids to the queue, skipping already-analysed / already-queued / dead ones."""
        accepted: list[str] = []
        with self._lock:
            for cid in conversation_ids:
                if cid in self._queued or cid in self._dead:
                    continue
                if self._store.is_analysed(cid):
                    continue
                try:
                    self._q.put_nowait(cid)
                except queue.Full:
                    break  # backpressure: stop accepting when full
                self._queued.add(cid)
                self._queued_at[cid] = datetime.now(timezone.utc).isoformat()
                accepted.append(cid)
        if accepted:
            self._store.mark_analyzing(accepted)
        return accepted

    def stats(self, limit: int = 100, offset: int = 0) -> dict:
        with self._lock:
            items = [
                {
                    "conversation_id": cid,
                    "status": "retrying" if cid in self._retrying else "analysing" if cid in self._in_flight else "queued",
                    "attempt": self._attempts.get(cid, 0) + 1,
                    "queued_at": self._queued_at[cid],
                }
                for cid in sorted(self._queued, key=lambda item: self._queued_at[item])
            ]
            return {
                "queued": self._q.qsize(),
                "in_flight": len(self._in_flight),
                "in_flight_or_queued": len(self._queued),
                "dead_letter": len(self._dead),
                "capacity": self._q.maxsize,
                "workers": len(self._workers),
                "started": self._started,
                "items": items[offset : offset + limit],
                "limit": limit,
                "offset": offset,
            }

    # internals ---------------------------------------------------------------
    def _work(self) -> None:
        while True:
            try:
                first = self._q.get(timeout=1.0)  # block briefly → no busy-loop
            except queue.Empty:
                continue
            batch = [first]
            while len(batch) < self._batch_size:
                try:
                    batch.append(self._q.get_nowait())
                except queue.Empty:
                    break
            with self._lock:
                self._in_flight.update(batch)
            try:
                self._process(batch)
            except Exception as exc:  # noqa: BLE001 - a worker must never die
                print(f"[warn] queue worker error: {type(exc).__name__}", flush=True)
                self._retry_or_dead(batch)
            finally:
                for _ in batch:
                    self._q.task_done()

    def _process(self, ids: list[str]) -> None:
        from .chatdb import load_from_chatdb
        from .deidentify import deidentify

        now = datetime.now(timezone.utc).isoformat()
        try:
            convs = load_from_chatdb(ids=ids)
        except Exception:  # transient (e.g. chat DB blip) → retry the whole batch
            self._retry_or_dead(ids)
            return

        found = {c.id: c for c in convs}
        try:
            records = {r.conversation_id: r for r in self._analyze(list(found.values()), f"q_{now}", now)}
        except Exception:  # analyser hard-failed for this batch
            records = {}

        for cid in ids:
            if self._store.is_analysed(cid):  # analysed meanwhile (e.g. on-demand) → no re-run
                self._finish(cid)
                continue
            conv = found.get(cid)
            if conv is None:  # id no longer exists in the source → don't retry forever
                self._finish(cid)
                continue
            rec = records.get(cid)
            if rec is not None:
                self._store.upsert(rec, deidentify(conv))
                self._store.record_analysis(cid, now)
                self._finish(cid)
            else:
                self._retry_or_dead([cid])

    def _finish(self, cid: str) -> None:
        with self._lock:
            self._queued.discard(cid)
            self._in_flight.discard(cid)
            self._retrying.discard(cid)
            self._queued_at.pop(cid, None)
            self._attempts.pop(cid, None)
        self._store.clear_analyzing(cid)

    def _retry_or_dead(self, ids: list[str]) -> None:
        for cid in ids:
            with self._lock:
                n = self._attempts.get(cid, 0) + 1
                self._attempts[cid] = n
                self._in_flight.discard(cid)
                give_up = n >= self._max_attempts
                if not give_up:
                    self._retrying.add(cid)
            if give_up:
                with self._lock:
                    self._queued.discard(cid)
                    self._retrying.discard(cid)
                    self._queued_at.pop(cid, None)
                    self._dead.add(cid)
                    self._attempts.pop(cid, None)
                self._store.mark_failed(cid)  # visible as unanalysed; never retried again
                self._store.clear_analyzing(cid)
            else:
                time.sleep(min(2 ** n, 10))  # backoff, then requeue
                try:
                    self._q.put_nowait(cid)
                    with self._lock:
                        self._retrying.discard(cid)
                except queue.Full:
                    self._finish(cid)  # can't requeue → release (a later sweep can re-add)
