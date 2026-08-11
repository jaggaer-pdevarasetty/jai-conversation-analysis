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
from .domain.models import AnalysisRecord, Conversation, RunSummary
from .store import CommonStore

INACTIVITY = timedelta(minutes=5)

# A batch analyzer maps a list of conversations -> records; conversations whose analysis
# hard-failed are omitted from the result (so the run marks them for retry). May raise.
BatchAnalyzer = Callable[[list[Conversation], str, str], list[AnalysisRecord]]


def _rules_batch(convs: list[Conversation], run_id: str, now: str) -> list[AnalysisRecord]:
    from .domain.analyze import analyze

    return [analyze(c, run_id, now) for c in convs]


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse(ts: str) -> datetime:
    # Normalise to an aware UTC datetime (LangSmith timestamps are often tz-naive).
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def last_activity(conv: Conversation) -> datetime:
    stamps: list[datetime] = []
    for raw in [m.created_at for m in conv.messages] + [conv.created_at]:
        if raw:
            try:
                stamps.append(_parse(raw))
            except ValueError:
                pass  # ignore unparseable timestamps
    return max(stamps) if stamps else _EPOCH  # no timestamp → treat as old → eligible


def is_eligible(conv: Conversation, now: datetime) -> bool:
    return (now - last_activity(conv)) >= INACTIVITY


def run_analysis(
    store: CommonStore,
    conversations: list[Conversation],
    now: datetime | None = None,
    analyze_batch: BatchAnalyzer = _rules_batch,
) -> RunSummary:
    now = now or datetime.now(timezone.utc)
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    started = now.isoformat()
    skipped = 0

    # Eligible (inactive >=5m, AC-11) and not already analysed (idempotent).
    eligible: list[Conversation] = []
    for conv in conversations:
        if not is_eligible(conv, now):
            skipped += 1
            continue
        if not store.is_analysed(conv.id):
            eligible.append(conv)

    analysed = failed = 0
    if eligible:
        try:
            records = analyze_batch(eligible, run_id, now.isoformat())
        except Exception:
            records = []  # total failure → all retried next run (AC-9)
        by_id = {r.conversation_id: r for r in records}
        for conv in eligible:
            record = by_id.get(conv.id)
            if record is None:
                store.mark_failed(conv.id)  # retried next run; count stays visible (AC-9)
                failed += 1
            else:
                store.upsert(record, deidentify(conv))
                analysed += 1

    return RunSummary(
        run_id=run_id,
        started_at=started,
        completed_at=datetime.now(timezone.utc).isoformat(),
        analysed=analysed,
        failed=failed,
        skipped=skipped,
    )
