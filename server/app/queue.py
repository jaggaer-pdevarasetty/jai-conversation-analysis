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
- **Environment-aware:** every item is an (environment, conversation_id) pair so UIT and PROD
  are loaded from the right chat DB and stored with strict isolation (ADR-0020).

At multi-instance scale, swap the internal `queue.Queue` for Redis / Cloud Tasks / PubSub —
the `enqueue()` contract and worker loop stay the same.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

from .config import settings

Item = tuple[str, str]  # (environment, conversation_id)


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
        self._q: queue.Queue[Item] = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._queued: set[Item] = set()  # in queue OR in-flight (dedup)
        self._in_flight: set[Item] = set()
        self._retrying: set[Item] = set()
        self._queued_at: dict[Item, str] = {}
        self._attempts: dict[Item, int] = {}
        self._dead: set[Item] = set()
        self._batch_size = batch_size or settings.batch_size
        self._max_attempts = max_attempts
        self._workers = [threading.Thread(target=self._work, name=f"analyzer-{i}", daemon=True) for i in range(workers)]
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._started = True
            for w in self._workers:
                w.start()

    def enqueue(self, conversation_ids: list[str], env: str = "uit") -> list[str]:
        """Add ids to the queue for an environment, skipping already-analysed / queued / dead."""
        accepted: list[str] = []
        with self._lock:
            for cid in conversation_ids:
                item = (env, cid)
                if item in self._queued or item in self._dead:
                    continue
                if self._store.is_analysed(cid, env):
                    continue
                try:
                    self._q.put_nowait(item)
                except queue.Full:
                    break  # backpressure: stop accepting when full
                self._queued.add(item)
                self._queued_at[item] = datetime.now(timezone.utc).isoformat()
                accepted.append(cid)
        if accepted:
            self._store.mark_analyzing(accepted, env)
        return accepted

    def stats(self, limit: int = 100, offset: int = 0) -> dict:
        with self._lock:
            items = [
                {
                    "conversation_id": cid,
                    "environment": env,
                    "status": "retrying" if (env, cid) in self._retrying else "analysing" if (env, cid) in self._in_flight else "queued",
                    "attempt": self._attempts.get((env, cid), 0) + 1,
                    "queued_at": self._queued_at[(env, cid)],
                }
                for (env, cid) in sorted(self._queued, key=lambda it: self._queued_at[it])
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
                # group by environment so each is loaded from its own chat DB
                by_env: dict[str, list[str]] = defaultdict(list)
                for env, cid in batch:
                    by_env[env].append(cid)
                for env, cids in by_env.items():
                    self._process(cids, env)
            except Exception as exc:  # noqa: BLE001 - a worker must never die
                print(f"[warn] queue worker error: {type(exc).__name__}", flush=True)
                self._retry_or_dead(batch)
            finally:
                for _ in batch:
                    self._q.task_done()

    def _process(self, ids: list[str], env: str) -> None:
        from .chatdb import load_from_chatdb
        from .deidentify import deidentify

        now = datetime.now(timezone.utc).isoformat()
        try:
            convs = load_from_chatdb(ids=ids, env=env)
        except Exception:  # transient (e.g. chat DB blip) → retry the whole batch
            self._retry_or_dead([(env, cid) for cid in ids])
            return

        found = {c.id: c for c in convs}
        # Only analyse conversations that actually have a transcript — a message-less
        # conversation has nothing to classify and would otherwise get a hallucinated label.
        analysable = [c for c in found.values() if c.messages]
        try:
            records = {r.conversation_id: r for r in self._analyze(analysable, f"q_{now}", now)}
        except Exception:  # analyser hard-failed for this batch
            records = {}

        for cid in ids:
            if self._store.is_analysed(cid, env):  # analysed meanwhile → no re-run
                self._finish(env, cid)
                continue
            conv = found.get(cid)
            if conv is None:  # id no longer exists in the source → don't retry forever
                self._finish(env, cid)
                continue
            if not conv.messages:  # no transcript → skip (don't analyse, don't retry forever)
                self._finish(env, cid)
                continue
            rec = records.get(cid)
            if rec is not None:
                self._store.upsert(rec, deidentify(conv))
                self._store.record_analysis(cid, now, env)
                self._finish(env, cid)
            else:
                self._retry_or_dead([(env, cid)])

    def _finish(self, env: str, cid: str) -> None:
        item = (env, cid)
        with self._lock:
            self._queued.discard(item)
            self._in_flight.discard(item)
            self._retrying.discard(item)
            self._queued_at.pop(item, None)
            self._attempts.pop(item, None)
        self._store.clear_analyzing(cid, env)

    def _retry_or_dead(self, items: list[Item]) -> None:
        for item in items:
            env, cid = item
            with self._lock:
                n = self._attempts.get(item, 0) + 1
                self._attempts[item] = n
                self._in_flight.discard(item)
                give_up = n >= self._max_attempts
                if not give_up:
                    self._retrying.add(item)
            if give_up:
                with self._lock:
                    self._queued.discard(item)
                    self._retrying.discard(item)
                    self._queued_at.pop(item, None)
                    self._dead.add(item)
                    self._attempts.pop(item, None)
                self._store.mark_failed(cid, env)  # visible as unanalysed; never retried again
                self._store.clear_analyzing(cid, env)
            else:
                time.sleep(min(2 ** n, 10))  # backoff, then requeue
                try:
                    self._q.put_nowait(item)
                    with self._lock:
                        self._retrying.discard(item)
                except queue.Full:
                    self._finish(env, cid)  # can't requeue → release (a later sweep can re-add)
