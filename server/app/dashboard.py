"""Admin dashboard read model: tenant -> user -> conversation drill-down (READ-ONLY).

Reads the chat DB for the tenant/user/conversation tree and joins our own analysis store
(by conversation_id) for the category / next step / confidence.

NOTE (privacy): this is an AUTHORISED admin view that intentionally shows tenant + user
identity, which is broader than the pooled, de-identified reviewer area described in
ADR-0007 / AC-10. Keep access restricted to internal reviewers.
"""

from __future__ import annotations

from sqlalchemy import bindparam, text

from .chatdb import _engine, safe_schema
from .store import CommonStore


def _sch() -> str:
    return safe_schema()


def overview(store: CommonStore) -> dict:
    with _engine().connect() as c:
        row = c.execute(
            text(
                f'select count(distinct tenant_id) tenants, count(distinct user_id) users, '
                f'count(*) conversations from "{_sch()}".conversations where is_deleted = false'
            )
        ).mappings().first()
    counts = store.count_by_category()
    return {
        "tenants": row["tenants"],
        "users": row["users"],
        "conversations": row["conversations"],
        "analysed": sum(counts.values()),
        "unanalysed": store.unanalysed_count(),
        "counts": counts,
    }


def tenants() -> list[dict]:
    with _engine().connect() as c:
        rows = c.execute(
            text(
                f'select conv.tenant_id, t.name, count(*) conversations, '
                f'count(distinct conv.user_id) users '
                f'from "{_sch()}".conversations conv '
                f'left join "{_sch()}".tenants t on t.tenant_id = conv.tenant_id '
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


def users(tenant_id: str) -> list[dict]:
    with _engine().connect() as c:
        rows = c.execute(
            text(
                f'select conv.user_id, u.user_name, u.role, count(*) conversations '
                f'from "{_sch()}".conversations conv '
                f'left join "{_sch()}".users u '
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


def conversation_meta(ids: list[str]) -> dict[str, dict]:
    """Batch-fetch source metadata (tenant/user/title/timestamps) for conversation ids.
    Used to enrich the feedback table + conversation detail. READ-ONLY; one query (no N+1)."""
    if not ids:
        return {}
    stmt = text(
        f'select conv.id, conv.tenant_id, conv.user_id, conv.title, conv.status, '
        f'conv.created_at, conv.last_message_at, conv.message_count, '
        f't.name as tenant_name, u.user_name '
        f'from "{_sch()}".conversations conv '
        f'left join "{_sch()}".tenants t on t.tenant_id = conv.tenant_id '
        f'left join "{_sch()}".users u on u.user_id = conv.user_id and u.tenant_id = conv.tenant_id '
        f'where conv.id::text in :ids'
    ).bindparams(bindparam("ids", expanding=True))
    with _engine().connect() as c:
        rows = c.execute(stmt, {"ids": ids}).mappings().all()
    return {
        str(r["id"]): {
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
        for r in rows
    }


def feedback_message_ids(ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    stmt = text(
        f'select m.conversation_id, f.message_id from "{_sch()}".feedback f '
        f'join "{_sch()}".messages m on m.id = f.message_id '
        f'where m.conversation_id::text in :ids and f.rating is not null '
        f'order by m.conversation_id, m.sequence_num'
    ).bindparams(bindparam("ids", expanding=True))
    with _engine().connect() as c:
        rows = c.execute(stmt, {"ids": ids}).mappings().all()
    result: dict[str, str] = {}
    for row in rows:
        result.setdefault(str(row["conversation_id"]), str(row["message_id"]))
    return result


def user_conversations(
    store: CommonStore, tenant_id: str, user_id: str, limit: int = 25, offset: int = 0
) -> tuple[list[dict], int]:
    params = {"tid": int(tenant_id), "uid": int(user_id), "limit": limit, "offset": offset}
    with _engine().connect() as c:
        total = int(c.execute(
            text(
                f'select count(*) from "{_sch()}".conversations '
                f'where is_deleted = false and tenant_id = :tid and user_id = :uid'
            ),
            params,
        ).scalar_one())
        rows = c.execute(
            text(
                f'select id, title, status, last_message_at, message_count '
                f'from "{_sch()}".conversations '
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
