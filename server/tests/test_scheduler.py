"""Scheduler: fires the job periodically; disabled when interval <= 0."""

import time

from app.scheduler import Scheduler


def test_scheduler_runs_job_periodically():
    calls = {"n": 0}
    s = Scheduler(0.05, lambda: calls.__setitem__("n", calls["n"] + 1))
    s.start()
    time.sleep(0.2)
    s.stop()
    assert calls["n"] >= 2


def test_scheduler_disabled_when_interval_zero():
    calls = {"n": 0}
    s = Scheduler(0, lambda: calls.__setitem__("n", calls["n"] + 1))
    s.start()
    time.sleep(0.1)
    assert calls["n"] == 0
