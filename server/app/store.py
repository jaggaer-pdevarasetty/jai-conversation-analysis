"""Service-owned common store (ADR-0001, ADR-0007).

The ONLY place we write. Keyed by (environment, conversation_id); holds de-identified
transcripts + analysis records + failed/retry set. No tenant/user anywhere. Environments
(uit/prod) are strictly isolated — a lookup in one never returns the other's data (ADR-0020).
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

Key = tuple[str, str]  # (environment, conversation_id)


class CommonStore:
    def __init__(self) -> None:
        self._analyses: dict[Key, AnalysisRecord] = {}
        self._conversations: dict[Key, CommonConversation] = {}
        self._failed: dict[Key, str] = {}  # (env,id) -> source region ("" = unknown)
        self._events: dict[Key, list[str]] = {}  # (env,id) -> ISO analyse timestamps
        self._analyzing: set[Key] = set()  # transient: in-flight lazy/background analyses
        self._override_events: dict[Key, list[Override]] = {}  # append-only override audit

    @staticmethod
    def _k(env: str, conversation_id: str) -> Key:
        return (env or "uit", conversation_id)

    # in-progress bookkeeping (lazy analyse) ----------------------------------
    def mark_analyzing(self, conversation_ids: list[str], env: str = "uit") -> None:
        self._analyzing.update(self._k(env, cid) for cid in conversation_ids)

    def clear_analyzing(self, conversation_id: str, env: str = "uit") -> None:
        self._analyzing.discard(self._k(env, conversation_id))

    def is_analyzing(self, conversation_id: str, env: str = "uit") -> bool:
        return self._k(env, conversation_id) in self._analyzing

    # rate-limit bookkeeping (on-demand analyse) ------------------------------
    def record_analysis(self, conversation_id: str, at_iso: str, env: str = "uit") -> None:
        self._events.setdefault(self._k(env, conversation_id), []).append(at_iso)

    def analyses_today(self, conversation_id: str, today: str | None = None, env: str = "uit") -> int:
        today = today or date.today().isoformat()
        return sum(1 for ts in self._events.get(self._k(env, conversation_id), []) if ts.startswith(today))

    # writes ------------------------------------------------------------------
    def upsert(self, record: AnalysisRecord, conversation: CommonConversation) -> None:
        key = self._k(record.environment, record.conversation_id)  # idempotent per (env, id)
        self._analyses[key] = record
        self._conversations[key] = conversation
        self._failed.pop(key, None)

    def mark_failed(self, conversation_id: str, env: str = "uit", region: str = "") -> None:
        # `region` (when known) lets regional dashboards scope the backlog correctly; "" = the
        # failure happened where the source region wasn't available (batch load error etc.).
        key = self._k(env, conversation_id)
        if key not in self._analyses:
            self._failed[key] = region or ""

    def is_analysed(self, conversation_id: str, env: str = "uit") -> bool:
        return self._k(env, conversation_id) in self._analyses

    def analysed_ids(self, env: str = "uit") -> set[str]:
        """Already-analysed conversation ids in this environment (for 'fetch pending')."""
        return {cid for (e, cid) in self._analyses if e == env}

    def set_override(
        self, conversation_id: str, category: Category, actor: str, env: str = "uit"
    ) -> AnalysisRecord | None:
        record = self._analyses.get(self._k(env, conversation_id))
        if record is None:
            return None
        previous = record.category  # effective before this override (model label or prior override)
        record.override = Override(
            category=category, actor=actor, at=datetime.now(timezone.utc).isoformat(),
            previous_category=previous,
        )
        record.recommended_next_step = recommended_next_step(record.category)
        # Auditability (J1-93353): every override is retained — append-only, never rewritten.
        self._override_events.setdefault(self._k(env, conversation_id), []).append(record.override)
        return record

    def override_events(self, conversation_id: str, env: str = "uit") -> list[Override]:
        """Full override history for a conversation, oldest first (audit record)."""
        return list(self._override_events.get(self._k(env, conversation_id), []))

    # reads -------------------------------------------------------------------
    def get_analysis(self, conversation_id: str, env: str = "uit") -> AnalysisRecord | None:
        return self._analyses.get(self._k(env, conversation_id))

    def get_conversation(self, conversation_id: str, env: str = "uit") -> CommonConversation | None:
        return self._conversations.get(self._k(env, conversation_id))

    def get_conversations(
        self, conversation_ids: list[str], env: str = "uit"
    ) -> dict[str, CommonConversation]:
        out: dict[str, CommonConversation] = {}
        for cid in conversation_ids:
            conv = self._conversations.get(self._k(env, cid))
            if conv is not None:
                out[cid] = conv
        return out

    def list(
        self, category: Category | None = None, region: str | None = None, env: str = "uit"
    ) -> list[AnalysisRecord]:
        items = [r for (e, _), r in self._analyses.items() if e == env]
        if category:
            items = [r for r in items if r.category == category]
        if region:  # strict region filter — no cross-region leakage
            items = [r for r in items if r.region == region]
        return sorted(items, key=lambda r: r.analyzed_at)

    def count_by_category(self, region: str | None = None, env: str = "uit") -> dict[str, int]:
        counts: dict[str, int] = {c: 0 for c in CATEGORIES}
        for (e, _), r in self._analyses.items():
            if e != env:
                continue
            if region and r.region != region:
                continue
            counts[r.category] += 1
        return counts

    def unanalysed_count(self, env: str = "uit", region: str | None = None) -> int:
        """Failed/unanalysed conversations. Region-scoped when `region` is given (failures whose
        source region is unknown — "" — only appear in the env-wide count, never a region's)."""
        if region is None:
            return sum(1 for (e, _) in self._failed if e == env)
        return sum(1 for (e, _), r in self._failed.items() if e == env and r == region)
