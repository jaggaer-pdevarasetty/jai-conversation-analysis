"""Admin dashboard read model: tenant -> user -> conversation drill-down (READ-ONLY).

Reads the chat DB for the tenant/user/conversation tree and joins our own analysis store
(by conversation_id) for the category / next step / confidence.

NOTE (privacy): this is an AUTHORISED admin view that intentionally shows tenant + user
identity, which is broader than the pooled, de-identified reviewer area described in
ADR-0007 / AC-10. Keep access restricted to internal reviewers.
"""

from __future__ import annotations

from sqlalchemy import text

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


def user_conversations(store: CommonStore, tenant_id: str, user_id: str) -> list[dict]:
    with _engine().connect() as c:
        rows = c.execute(
            text(
                f'select id, title, status, last_message_at, message_count '
                f'from "{_sch()}".conversations '
                f'where is_deleted = false and tenant_id = :tid and user_id = :uid '
                f'order by last_message_at desc nulls last'
            ),
            {"tid": int(tenant_id), "uid": int(user_id)},
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
    return out
