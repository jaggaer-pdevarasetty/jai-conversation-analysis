"""Admin dashboard read model: tenant -> user -> conversation drill-down (READ-ONLY).

Reads the chat DB for the tenant/user/conversation tree and joins our own analysis store
(by conversation_id) for the category / next step / confidence.

Multi-region: the drill-down targets ONE region (the `region` arg, default = first
configured); enrichment (conversation_meta / feedback ids) spans ALL configured regions and
silently skips any that are unreachable (e.g. permission denied), so one bad region can't
break the view or leak another region's rows.

NOTE (privacy): this is an AUTHORISED admin view that intentionally shows tenant + user
identity, broader than the pooled area (ADR-0007 / AC-10). Keep access restricted.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import bindparam, text

from .chatdb import _engine_for, region_labels, resolve_region, safe_schema
from .store import CommonStore


@contextmanager
def _connect(region: str | None):
    """A connection + validated schema for one region; disposes the engine after use."""
    r = resolve_region(region)
    if r is None:
        raise RuntimeError("no chat DB region configured (set REGIONS/REGION_*_CHAT_DB_URL)")
    eng = _engine_for(r.url, r.db_name)
    try:
        with eng.connect() as c:
            yield c, safe_schema(r.schema)
    finally:
        eng.dispose()


def overview(store: CommonStore, region: str | None = None) -> dict:
    with _connect(region) as (c, sch):
        row = c.execute(
            text(
                f'select count(distinct tenant_id) tenants, count(distinct user_id) users, '
                f'count(*) conversations from "{sch}".conversations where is_deleted = false'
            )
        ).mappings().first()
    counts = store.count_by_category(region=region)
    return {
        "region": region,
        "tenants": row["tenants"],
        "users": row["users"],
        "conversations": row["conversations"],
        "analysed": sum(counts.values()),
        "unanalysed": store.unanalysed_count(),
        "counts": counts,
    }


def tenants(region: str | None = None) -> list[dict]:
    with _connect(region) as (c, sch):
        rows = c.execute(
            text(
                f'select conv.tenant_id, t.name, count(*) conversations, '
                f'count(distinct conv.user_id) users '
                f'from "{sch}".conversations conv '
                f'left join "{sch}".tenants t on t.tenant_id = conv.tenant_id '
                f'where conv.is_deleted = false '
                f'group by conv.tenant_id, t.name order by conversations desc'
            )
        ).mappings().all()
    return [
        {
            "tenant_id": str(r["tenant_id"]),
            "name": r["name"] or f"Tenant {r['tenant_id']}",
            "conversations": r["conversations"],
            "users": r["users"],
        }
        for r in rows
    ]


def users(tenant_id: str, region: str | None = None) -> list[dict]:
    with _connect(region) as (c, sch):
        rows = c.execute(
            text(
                f'select conv.user_id, u.user_name, u.role, count(*) conversations '
                f'from "{sch}".conversations conv '
                f'left join "{sch}".users u '
                f'  on u.user_id = conv.user_id and u.tenant_id = conv.tenant_id '
                f'where conv.is_deleted = false and conv.tenant_id = :tid '
                f'group by conv.user_id, u.user_name, u.role order by conversations desc'
            ),
            {"tid": int(tenant_id)},
        ).mappings().all()
    return [
        {
            "user_id": str(r["user_id"]),
            "user_name": r["user_name"] or f"User {r['user_id']}",
            "role": r["role"],
            "conversations": r["conversations"],
        }
        for r in rows
    ]


def conversation_meta(ids: list[str], region: str | None = None) -> dict[str, dict]:
    """Source metadata (tenant/user/title/timestamps) for conversation ids, across regions.
    One query per region (no N+1). Unreachable regions are skipped (resilient)."""
    if not ids:
        return {}
    from .privacy import apply_meta

    def _sql(sch: str):
        return text(
            f'select conv.id, conv.tenant_id, conv.user_id, conv.title, conv.status, '
            f'conv.created_at, conv.last_message_at, conv.message_count, '
            f't.name as tenant_name, u.user_name '
            f'from "{sch}".conversations conv '
            f'left join "{sch}".tenants t on t.tenant_id = conv.tenant_id '
            f'left join "{sch}".users u on u.user_id = conv.user_id and u.tenant_id = conv.tenant_id '
            f'where conv.id::text in :ids'
        ).bindparams(bindparam("ids", expanding=True))

    labels = [region] if region else (region_labels() or [None])
    out: dict[str, dict] = {}
    for label in labels:
        try:
            with _connect(label) as (c, sch):
                rows = c.execute(_sql(sch), {"ids": ids}).mappings().all()
        except Exception:  # noqa: BLE001 - region unreachable (e.g. permission denied) → skip
            continue
        for r in rows:
            out.setdefault(
                str(r["id"]),
                apply_meta(
                    {
                        "region": label,
                        "tenant_id": str(r["tenant_id"]) if r["tenant_id"] is not None else None,
                        "tenant_name": r["tenant_name"] or (f"Tenant {r['tenant_id']}" if r["tenant_id"] else None),
                        "user_id": str(r["user_id"]) if r["user_id"] is not None else None,
                        "user_name": r["user_name"] or (f"User {r['user_id']}" if r["user_id"] else None),
                        "title": r["title"],
                        "status": r["status"],
                        "created_at": str(r["created_at"]) if r["created_at"] else None,
                        "last_message_at": str(r["last_message_at"]) if r["last_message_at"] else None,
                        "message_count": r["message_count"],
                    }
                ),
            )
    return out


def user_conversations(
    store: CommonStore, tenant_id: str, user_id: str, limit: int = 25, offset: int = 0,
    region: str | None = None,
) -> tuple[list[dict], int]:
    params = {"tid": int(tenant_id), "uid": int(user_id), "limit": limit, "offset": offset}
    with _connect(region) as (c, sch):
        total = int(c.execute(
            text(
                f'select count(*) from "{sch}".conversations '
                f'where is_deleted = false and tenant_id = :tid and user_id = :uid'
            ),
            params,
        ).scalar_one())
        rows = c.execute(
            text(
                f'select id, title, status, last_message_at, message_count '
                f'from "{sch}".conversations '
                f'where is_deleted = false and tenant_id = :tid and user_id = :uid '
                f'order by last_message_at desc nulls last limit :limit offset :offset'
            ),
            params,
        ).mappings().all()
    out = []
    for r in rows:
        cid = str(r["id"])
        rec = store.get_analysis(cid)
        if rec is not None:
            status = "analysed"
        elif store.is_analyzing(cid):
            status = "analysing"
        else:
            status = "pending"
        out.append(
            {
                "conversation_id": cid,
                "title": r["title"],
                "message_count": r["message_count"],
                "last_message_at": str(r["last_message_at"]) if r["last_message_at"] else None,
                "analysed": rec is not None,
                "status": status,
                "category": rec.category if rec else None,
                "confidence": rec.confidence if rec else None,
                "recommended_next_step": rec.recommended_next_step if rec else None,
            }
        )
    return out, total
