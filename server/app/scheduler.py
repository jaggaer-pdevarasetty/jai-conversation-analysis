"""Periodic scheduler (Phase A) — runs the analysis sweep every N hours.

Deliberately dependency-free: a daemon thread that waits `interval` then runs `job`, looping.
`job` enqueues eligible, not-yet-analysed conversations into the AnalysisQueue (which dedupes,
so a sweep never re-runs already-analysed chats). SCHEDULE_HOURS=0 disables it.

Single-instance only. For multiple instances, use a real scheduler with leader election
(e.g. Cloud Scheduler → one endpoint, or APScheduler with a shared lock).
"""

from __future__ import annotations

import threading
from collections.abc import Callable


class Scheduler:
    def __init__(self, interval_seconds: float, job: Callable[[], None]) -> None:
        self._interval = interval_seconds
        self._job = job
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._interval <= 0 or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        # wait() returns True only when stopped → loops until then
        while not self._stop.wait(self._interval):
            try:
                self._job()
            except Exception as exc:  # noqa: BLE001 - a scheduler tick must never crash the app
                print(f"[warn] scheduled sweep failed: {type(exc).__name__}", flush=True)
