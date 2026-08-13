"""Service-owned common store (ADR-0001, ADR-0007).

The ONLY place we write. Keyed by conversation_id; holds de-identified transcripts +
analysis records + failed/retry set. No tenant/user anywhere.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from .domain.models import (
    CATEGORIES,
    AnalysisRecord,
    Category,
    CommonConversation,
    Override,
)
from .domain.category import recommended_next_step


class CommonStore:
    def __init__(self) -> None:
        self._analyses: dict[str, AnalysisRecord] = {}
        self._conversations: dict[str, CommonConversation] = {}
        self._failed: set[str] = set()
        self._events: dict[str, list[str]] = {}  # conversation_id -> ISO analyse timestamps
        self._analyzing: set[str] = set()  # transient: in-flight lazy/background analyses

    # in-progress bookkeeping (lazy analyse) ----------------------------------
    def mark_analyzing(self, conversation_ids: list[str]) -> None:
        self._analyzing.update(conversation_ids)

    def clear_analyzing(self, conversation_id: str) -> None:
        self._analyzing.discard(conversation_id)

    def is_analyzing(self, conversation_id: str) -> bool:
        return conversation_id in self._analyzing

    # rate-limit bookkeeping (on-demand analyse) ------------------------------
    def record_analysis(self, conversation_id: str, at_iso: str) -> None:
        self._events.setdefault(conversation_id, []).append(at_iso)

    def analyses_today(self, conversation_id: str, today: str | None = None) -> int:
        today = today or date.today().isoformat()
        return sum(1 for ts in self._events.get(conversation_id, []) if ts.startswith(today))

    # writes ------------------------------------------------------------------
    def upsert(self, record: AnalysisRecord, conversation: CommonConversation) -> None:
        self._analyses[record.conversation_id] = record  # idempotent on conversation_id
        self._conversations[record.conversation_id] = conversation
        self._failed.discard(record.conversation_id)

    def mark_failed(self, conversation_id: str) -> None:
        if conversation_id not in self._analyses:
            self._failed.add(conversation_id)

    def is_analysed(self, conversation_id: str) -> bool:
        return conversation_id in self._analyses

    def set_override(self, conversation_id: str, category: Category, actor: str) -> AnalysisRecord | None:
        record = self._analyses.get(conversation_id)
        if record is None:
            return None
        record.override = Override(
            category=category, actor=actor, at=datetime.now(timezone.utc).isoformat()
        )
        record.recommended_next_step = recommended_next_step(record.category)
        return record

    # reads -------------------------------------------------------------------
    def get_analysis(self, conversation_id: str) -> AnalysisRecord | None:
        return self._analyses.get(conversation_id)

    def get_conversation(self, conversation_id: str) -> CommonConversation | None:
        return self._conversations.get(conversation_id)

    def get_conversations(self, conversation_ids: list[str]) -> dict[str, CommonConversation]:
        return {cid: self._conversations[cid] for cid in conversation_ids if cid in self._conversations}

    def list(
        self, category: Category | None = None, region: str | None = None
    ) -> list[AnalysisRecord]:
        items = list(self._analyses.values())
        if category:
            items = [r for r in items if r.category == category]
        if region:  # strict region filter — no cross-region leakage
            items = [r for r in items if r.region == region]
        return sorted(items, key=lambda r: r.analyzed_at)

    def count_by_category(self, region: str | None = None) -> dict[str, int]:
        counts: dict[str, int] = {c: 0 for c in CATEGORIES}
        for r in self._analyses.values():
            if region and r.region != region:
                continue
            counts[r.category] += 1
        return counts

    def unanalysed_count(self) -> int:
        return len(self._failed)
