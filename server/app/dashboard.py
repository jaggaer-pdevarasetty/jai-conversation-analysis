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
from functools import lru_cache

from sqlalchemy import bindparam, text

from .chatdb import _engine_for, _platform_layout, region_labels, resolve_region, safe_schema
from .store import CommonStore


def _timestamp(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value).replace(" ", "T", 1)


@lru_cache
def _dashboard_engine(url: str, db_name: str):
    return _engine_for(url, db_name)


@contextmanager
def _connect(region: str | None, env: str = "uit"):
    """A connection + validated schema for one region in an environment."""
    r = resolve_region(region, env)
    if r is None:
        raise RuntimeError("no chat DB region configured (set REGIONS/REGION_*_CHAT_DB_URL)")
    with _dashboard_engine(r.url, r.db_name).connect() as c:
        yield c, safe_schema(r.schema)


def _scan_labels(region: str | None, env: str = "uit") -> list[str | None]:
    """Regions to query: just the one requested, or ALL configured regions of the env when
    region is None ('All regions'). Falls back to [None] (legacy single region) if none set."""
    if region:
        return [region]
    return list(region_labels(env)) or [None]


def overview(store: CommonStore, region: str | None = None, env: str = "uit") -> dict:
    # 'All regions' (region=None) combines every configured region; unreachable regions are
    # skipped so one bad region can't blank the overview. Tenants/users are counted DISTINCT
    # across regions (union of ids) so the stat cards match the merged tenant directory even if
    # an identity spans regions; conversations are region-unique so they're summed.
    tenant_ids: set[str] = set()
    user_ids: set[str] = set()
    conversations_n = 0
    for label in _scan_labels(region, env):
        try:
            with _connect(label, env) as (c, sch):
                table = "threads" if _platform_layout(c, sch) else "conversations"
                where = "" if table == "threads" else " where is_deleted = false"
                for r in c.execute(text(f'select distinct tenant_id, user_id from "{sch}".{table}{where}')).all():
                    if r[0] is not None:
                        tenant_ids.add(str(r[0]))
                    if r[1] is not None:
                        user_ids.add(str(r[1]))
                conversations_n += int(
                    c.execute(text(f'select count(*) from "{sch}".{table}{where}')).scalar_one()
                )
        except Exception:  # noqa: BLE001 - region unreachable → skip, don't fail the overview
            continue
    records = store.list(region=region, env=env)
    counts = store.count_by_category(region=region, env=env)
    telemetry_complete = sum(
        record.metrics.ttft_ms is not None
        and record.metrics.input_tokens is not None
        and record.metrics.output_tokens is not None
        for record in records
    )
    return {
        "region": region,
        "tenants": len(tenant_ids),
        "users": len(user_ids),
        "conversations": conversations_n,
        "analysed": sum(counts.values()),
        "unanalysed": store.unanalysed_count(env=env),
        "counts": counts,
        "telemetry_complete": telemetry_complete,
        "telemetry_total": len(records),
    }


def tenants(region: str | None = None, env: str = "uit") -> list[dict]:
    # Merge tenants across all regions when region is None (same tenant in two regions is
    # combined). Unreachable regions are skipped.
    merged: dict[str, dict] = {}
    for label in _scan_labels(region, env):
        try:
            with _connect(label, env) as (c, sch):
                if _platform_layout(c, sch):
                    rows = c.execute(
                        text(
                            f'select conv.tenant_id, t.name, count(*) conversations, '
                            f'count(distinct conv.user_id) users '
                            f'from "{sch}".threads conv '
                            f'left join "{sch}".tenants t on t.id::text = conv.tenant_id '
                            f'group by conv.tenant_id, t.name order by conversations desc'
                        )
                    ).mappings().all()
                else:
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
        except Exception:  # noqa: BLE001 - region unreachable → skip
            continue
        for r in rows:
            tid = str(r["tenant_id"])
            m = merged.setdefault(tid, {"name": None, "conversations": 0, "users": 0})
            m["conversations"] += r["conversations"] or 0
            m["users"] += r["users"] or 0
            m["name"] = m["name"] or r["name"]
    out = [
        {
            "tenant_id": tid,
            "name": m["name"] or f"Tenant {tid}",
            "conversations": m["conversations"],
            "users": m["users"],
        }
        for tid, m in merged.items()
    ]
    out.sort(key=lambda x: x["conversations"], reverse=True)
    return out


def users(tenant_id: str, region: str | None = None, env: str = "uit") -> list[dict]:
    # A tenant lives in one region in practice, but scan all when region is None so the drill-down
    # works regardless of which region the tenant is in. Regions that are unreachable — or whose
    # schema can't match this tenant_id (e.g. non-numeric id on a standard schema) — are skipped.
    merged: dict[str, dict] = {}
    for label in _scan_labels(region, env):
        try:
            with _connect(label, env) as (c, sch):
                if _platform_layout(c, sch):
                    rows = c.execute(
                        text(
                            f'select conv.user_id, u.name as user_name, '
                            f'case when u.admin then \'admin\' else null end role, count(*) conversations '
                            f'from "{sch}".threads conv '
                            f'left join "{sch}".users u on u.id = conv.user_id '
                            f'where conv.tenant_id = :tid '
                            f'group by conv.user_id, u.name, u.admin order by conversations desc'
                        ),
                        {"tid": tenant_id},
                    ).mappings().all()
                else:
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
        except Exception:  # noqa: BLE001 - region unreachable / tenant_id not valid here → skip
            continue
        for r in rows:
            uid = str(r["user_id"])
            m = merged.setdefault(uid, {"user_name": None, "role": None, "conversations": 0})
            m["conversations"] += r["conversations"] or 0
            m["user_name"] = m["user_name"] or r["user_name"]
            m["role"] = m["role"] or r["role"]
    out = [
        {
            "user_id": uid,
            "user_name": m["user_name"] or f"User {uid}",
            "role": m["role"],
            "conversations": m["conversations"],
        }
        for uid, m in merged.items()
    ]
    out.sort(key=lambda x: x["conversations"], reverse=True)
    return out


def conversation_meta(ids: list[str], region: str | None = None, env: str = "uit") -> dict[str, dict]:
    """Source metadata (tenant/user/title/timestamps) for conversation ids, across regions.
    One query per region (no N+1). Unreachable regions are skipped (resilient)."""
    if not ids:
        return {}
    from .privacy import apply_meta

    def _sql(sch: str, platform: bool):
        if platform:
            return text(
                f'select conv.id, conv.tenant_id, conv.user_id, conv.title, conv.status, '
                f'conv.created_at, conv.updated_at last_message_at, '
                f'(select count(*) from "{sch}".thread_messages msg where msg.thread_id = conv.id) message_count, '
                f't.name as tenant_name, u.name as user_name '
                f'from "{sch}".threads conv '
                f'left join "{sch}".tenants t on t.id::text = conv.tenant_id '
                f'left join "{sch}".users u on u.id = conv.user_id '
                f'where conv.id::text in :ids'
            ).bindparams(bindparam("ids", expanding=True))
        return text(
            f'select conv.id, conv.tenant_id, conv.user_id, conv.title, conv.status, '
            f'conv.created_at, conv.last_message_at, conv.message_count, '
            f't.name as tenant_name, u.user_name '
            f'from "{sch}".conversations conv '
            f'left join "{sch}".tenants t on t.tenant_id = conv.tenant_id '
            f'left join "{sch}".users u on u.user_id = conv.user_id and u.tenant_id = conv.tenant_id '
            f'where conv.id::text in :ids'
        ).bindparams(bindparam("ids", expanding=True))

    labels = [region] if region else (region_labels(env) or [None])
    out: dict[str, dict] = {}
    for label in labels:
        try:
            with _connect(label, env) as (c, sch):
                rows = c.execute(_sql(sch, _platform_layout(c, sch)), {"ids": ids}).mappings().all()
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
                        "created_at": _timestamp(r["created_at"]),
                        "last_message_at": _timestamp(r["last_message_at"]),
                        "message_count": r["message_count"],
                    }
                ),
            )
    return out


def user_conversations(
    store: CommonStore, tenant_id: str, user_id: str, limit: int = 25, offset: int = 0,
    region: str | None = None, env: str = "uit",
) -> tuple[list[dict], int]:
    # A tenant/user lives in one region, but scan all when region is None so the drill-down
    # works regardless of which region owns them. Skip regions that are unreachable or whose
    # schema can't match this id (e.g. a non-numeric id on a classic schema).
    rows: list = []
    total = 0
    for label in _scan_labels(region, env):
        try:
            with _connect(label, env) as (c, sch):
                if _platform_layout(c, sch):
                    params = {"tid": tenant_id, "uid": user_id, "limit": limit, "offset": offset}
                    total += int(c.execute(
                        text(f'select count(*) from "{sch}".threads where tenant_id = :tid and user_id = :uid'),
                        params,
                    ).scalar_one())
                    rows += c.execute(
                        text(
                            f'select thread.id, thread.title, thread.status, thread.updated_at last_message_at, '
                            f'(select count(*) from "{sch}".thread_messages msg where msg.thread_id = thread.id) message_count '
                            f'from "{sch}".threads thread where tenant_id = :tid and user_id = :uid '
                            f'order by updated_at desc limit :limit offset :offset'
                        ),
                        params,
                    ).mappings().all()
                else:
                    params = {"tid": int(tenant_id), "uid": int(user_id), "limit": limit, "offset": offset}
                    total += int(c.execute(
                        text(
                            f'select count(*) from "{sch}".conversations '
                            f'where is_deleted = false and tenant_id = :tid and user_id = :uid'
                        ),
                        params,
                    ).scalar_one())
                    rows += c.execute(
                        text(
                            f'select id, title, status, last_message_at, message_count '
                            f'from "{sch}".conversations '
                            f'where is_deleted = false and tenant_id = :tid and user_id = :uid '
                            f'order by last_message_at desc nulls last limit :limit offset :offset'
                        ),
                        params,
                    ).mappings().all()
        except Exception:  # noqa: BLE001 - region unreachable / id not valid here → skip
            continue
    out = []
    for r in rows:
        cid = str(r["id"])
        rec = store.get_analysis(cid, env)
        if rec is not None:
            status = "analysed"
        elif store.is_analyzing(cid, env):
            status = "analysing"
        else:
            status = "pending"
        out.append(
            {
                "conversation_id": cid,
                "title": r["title"],
                "message_count": r["message_count"],
                "last_message_at": _timestamp(r["last_message_at"]),
                "analysed": rec is not None,
                "status": status,
                "category": rec.category if rec else None,
                "confidence": rec.confidence if rec else None,
                "recommended_next_step": rec.recommended_next_step if rec else None,
            }
        )
    return out, total
