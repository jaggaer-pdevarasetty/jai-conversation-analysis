"""Scheduled batch run: eligibility + analyse + retry (ADR-0008).

Eligibility: a conversation is eligible once inactive >= 5 minutes (AC-11). Runs are
triggered every 4 hours in production (external scheduler). Failed analyses are retried
on the next run and their count stays visible (AC-9).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from .deidentify import deidentify
from .domain.analyze import analyze as default_analyze
from .domain.models import AnalysisRecord, Conversation, RunSummary
from .store import CommonStore

INACTIVITY = timedelta(minutes=5)

# A classifier maps (conversation, run_id, now_iso) -> AnalysisRecord; may raise.
Classifier = Callable[[Conversation, str, str], AnalysisRecord]


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def last_activity(conv: Conversation) -> datetime:
    stamps = [m.created_at for m in conv.messages if m.created_at] or [conv.created_at]
    return max(_parse(s) for s in stamps)


def is_eligible(conv: Conversation, now: datetime) -> bool:
    return (now - last_activity(conv)) >= INACTIVITY


def run_analysis(
    store: CommonStore,
    conversations: list[Conversation],
    now: datetime | None = None,
    classify: Classifier = default_analyze,
) -> RunSummary:
    now = now or datetime.now(timezone.utc)
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    started = now.isoformat()
    analysed = failed = skipped = 0

    for conv in conversations:
        if not is_eligible(conv, now):
            skipped += 1  # picked up by a later run (AC-11)
            continue
        if store.is_analysed(conv.id):
            continue  # idempotent
        try:
            record = classify(conv, run_id, now.isoformat())
            store.upsert(record, deidentify(conv))
            analysed += 1
        except Exception:
            store.mark_failed(conv.id)  # retried next run; count stays visible (AC-9)
            failed += 1

    return RunSummary(
        run_id=run_id,
        started_at=started,
        completed_at=datetime.now(timezone.utc).isoformat(),
        analysed=analysed,
        failed=failed,
        skipped=skipped,
    )
