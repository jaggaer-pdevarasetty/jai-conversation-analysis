"""Persistent common store (ADR-0009).

Same interface as the in-memory CommonStore, backed by SQLAlchemy on **PostgreSQL**
(RESULTS_DB_URL; run locally via podman/Docker — see docker-compose.postgres.yml). SQLite
is intentionally not used for storing data. Still conversation_id-only and de-identified
(ADR-0007) — no tenant/user columns.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from datetime import date

from sqlalchemy import (
    JSON,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    func,
    select,
    text,
)

from .domain.category import recommended_next_step
from .domain.models import (
    CATEGORIES,
    AnalysisRecord,
    Category,
    CommonConversation,
    DeepAnalysis,
    Feedback,
    Message,
    Metrics,
    Override,
    Signals,
)

_metadata = MetaData()
_analysis = Table(
    "analysis", _metadata,
    Column("conversation_id", String, primary_key=True),
    Column("category", String, index=True),  # effective category (for filter/count)
    Column("region", String, index=True),  # source region (us/eu/uk) — for filter/count
    Column("data", JSON),
)
_conversation = Table(
    "conversation", _metadata,
    Column("conversation_id", String, primary_key=True),
    Column("data", JSON),
)
_failed = Table(
    "failed", _metadata,
    Column("conversation_id", String, primary_key=True),
)
_analyze_event = Table(
    "analyze_event", _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", String, index=True),
    Column("at", String),  # ISO timestamp; daily cap counts by date prefix
)


def _rec_to_row(r: AnalysisRecord) -> dict:
    return {
        "conversation_id": r.conversation_id,
        "category": r.category,
        "region": r.region,
        "data": asdict(r),
    }


def _row_to_rec(data: dict) -> AnalysisRecord:
    d = dict(data)
    d["signals"] = Signals(**d["signals"])
    d["metrics"] = Metrics(**d["metrics"])
    d["override"] = Override(**d["override"]) if d.get("override") else None
    d["deep"] = DeepAnalysis(**d["deep"]) if d.get("deep") else None
    allowed = {field.name for field in fields(AnalysisRecord)}
    return AnalysisRecord(**{key: value for key, value in d.items() if key in allowed})


def _conv_to_row(c: CommonConversation) -> dict:
    return {"conversation_id": c.conversation_id, "data": asdict(c)}


def _row_to_conv(data: dict) -> CommonConversation:
    return CommonConversation(
        conversation_id=data["conversation_id"],
        messages=[Message(**m) for m in data["messages"]],
        feedback=Feedback(**data["feedback"]),
    )


class SqlResultStore:
    def __init__(self, url: str) -> None:
        self._engine = create_engine(url, future=True)
        _metadata.create_all(self._engine)
        # Idempotent migration: add `region` to a pre-existing analysis table (Postgres).
        with self._engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE analysis ADD COLUMN IF NOT EXISTS region VARCHAR"))
            except Exception:  # backend without IF NOT EXISTS / column already present
                pass
        self._analyzing: set[str] = set()  # transient runtime state (not persisted)

    # in-progress bookkeeping (lazy analyse) ----------------------------------
    def mark_analyzing(self, conversation_ids: list[str]) -> None:
        self._analyzing.update(conversation_ids)

    def clear_analyzing(self, conversation_id: str) -> None:
        self._analyzing.discard(conversation_id)

    def is_analyzing(self, conversation_id: str) -> bool:
        return conversation_id in self._analyzing

    def _put(self, conn, table: Table, key: str, row: dict) -> None:
        conn.execute(delete(table).where(table.c.conversation_id == key))
        conn.execute(table.insert().values(**row))

    def upsert(self, record: AnalysisRecord, conversation: CommonConversation) -> None:
        with self._engine.begin() as conn:
            self._put(conn, _analysis, record.conversation_id, _rec_to_row(record))
            self._put(conn, _conversation, conversation.conversation_id, _conv_to_row(conversation))
            conn.execute(delete(_failed).where(_failed.c.conversation_id == record.conversation_id))

    def mark_failed(self, conversation_id: str) -> None:
        if self.is_analysed(conversation_id):
            return
        with self._engine.begin() as conn:
            conn.execute(delete(_failed).where(_failed.c.conversation_id == conversation_id))
            conn.execute(_failed.insert().values(conversation_id=conversation_id))

    def is_analysed(self, conversation_id: str) -> bool:
        with self._engine.begin() as conn:
            return conn.execute(
                select(_analysis.c.conversation_id).where(_analysis.c.conversation_id == conversation_id)
            ).first() is not None

    def analysed_ids(self) -> set[str]:
        """All already-analysed conversation ids in one query (for the manual 'fetch pending' step)."""
        with self._engine.begin() as conn:
            return {r[0] for r in conn.execute(select(_analysis.c.conversation_id)).all()}

    def set_override(self, conversation_id: str, category: Category, actor: str) -> AnalysisRecord | None:
        from datetime import datetime, timezone

        record = self.get_analysis(conversation_id)
        if record is None:
            return None
        record.override = Override(category=category, actor=actor, at=datetime.now(timezone.utc).isoformat())
        record.recommended_next_step = recommended_next_step(record.category)
        with self._engine.begin() as conn:
            self._put(conn, _analysis, conversation_id, _rec_to_row(record))
        return record

    def get_analysis(self, conversation_id: str) -> AnalysisRecord | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(_analysis.c.data).where(_analysis.c.conversation_id == conversation_id)
            ).first()
        return _row_to_rec(row[0]) if row else None

    def get_conversation(self, conversation_id: str) -> CommonConversation | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(_conversation.c.data).where(_conversation.c.conversation_id == conversation_id)
            ).first()
        return _row_to_conv(row[0]) if row else None

    def get_conversations(self, conversation_ids: list[str]) -> dict[str, CommonConversation]:
        if not conversation_ids:
            return {}
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(_conversation.c.conversation_id, _conversation.c.data).where(
                    _conversation.c.conversation_id.in_(conversation_ids)
                )
            ).all()
        return {conversation_id: _row_to_conv(data) for conversation_id, data in rows}

    def list(
        self, category: Category | None = None, region: str | None = None
    ) -> list[AnalysisRecord]:
        stmt = select(_analysis.c.data)
        if category:
            stmt = stmt.where(_analysis.c.category == category)
        if region:  # strict region filter — no cross-region leakage
            stmt = stmt.where(_analysis.c.region == region)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).all()
        return sorted((_row_to_rec(r[0]) for r in rows), key=lambda r: r.analyzed_at)

    def count_by_category(self, region: str | None = None) -> dict[str, int]:
        counts: dict[str, int] = {c: 0 for c in CATEGORIES}
        stmt = select(_analysis.c.category, func.count()).group_by(_analysis.c.category)
        if region:
            stmt = stmt.where(_analysis.c.region == region)
        with self._engine.begin() as conn:
            for cat, n in conn.execute(stmt).all():
                if cat in counts:
                    counts[cat] = n
        return counts

    def unanalysed_count(self) -> int:
        with self._engine.begin() as conn:
            return int(conn.execute(select(func.count()).select_from(_failed)).scalar_one())

    # rate-limit bookkeeping (on-demand analyse) ------------------------------
    def record_analysis(self, conversation_id: str, at_iso: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(_analyze_event.insert().values(conversation_id=conversation_id, at=at_iso))

    def analyses_today(self, conversation_id: str, today: str | None = None) -> int:
        today = today or date.today().isoformat()
        with self._engine.begin() as conn:
            return int(
                conn.execute(
                    select(func.count())
                    .select_from(_analyze_event)
                    .where(
                        _analyze_event.c.conversation_id == conversation_id,
                        _analyze_event.c.at.like(f"{today}%"),
                    )
                ).scalar_one()
            )
