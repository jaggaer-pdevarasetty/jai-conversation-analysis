"""Read REAL conversations from the chat DB (READ-ONLY / SELECT only; ADR-0001).

Schema `jai_agentos_schema_uit` (db `jai_agentos_uit`):
  conversations(id, tenant_id, user_id, title, status, last_message_at, created_at, is_deleted)
  messages(id, conversation_id, role, content, input_tokens, output_tokens, total_tokens,
           model, latency, status, error_message, sequence_num, created_at)
  feedback(message_id, rating BOOLEAN, comment)
  token_usage(message_id, total_input_tokens, total_output_tokens, elapsed_seconds)

Builds Conversation objects for the analyzer. tenant_id/user_id are carried source-side and
dropped by de-identify() (ADR-0007) before anything reaches the common store. We only SELECT.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import make_url

from .config import RegionConfig, settings
from .domain.models import Conversation, Feedback, Message

_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


def safe_schema(schema: str | None = None) -> str:
    """Whitelist the schema NAME (it's interpolated into SQL; values use bound params)."""
    sch = schema or settings.chat_db_schema
    if not _IDENT.match(sch):
        raise ValueError(f"invalid schema name: {sch!r}")
    return sch


def _primary_region() -> RegionConfig:
    """The single/primary region (used by tests with an explicit engine + the dashboard)."""
    return RegionConfig(
        label=os.getenv("REGION_LABEL", "uk"),
        url=settings.chat_db_url,
        db_name=settings.chat_db_name,
        schema=settings.chat_db_schema,
    )


def _engine_for(url: str, db_name: str):
    return create_engine(
        make_url(url).set(database=db_name), connect_args={"connect_timeout": 15}, pool_pre_ping=True
    )


def configured_regions(env: str = "uit") -> list[RegionConfig]:
    """All configured regions for an environment; UIT falls back to the legacy single region."""
    regs = settings.regions(env)
    if regs:
        return regs
    if env != "uit":
        return []
    primary = _primary_region()
    return [primary] if primary.url else []


def resolve_region(label: str | None, env: str = "uit") -> RegionConfig | None:
    """Region by label within an environment; if no label, the first configured region."""
    regs = configured_regions(env)
    if not regs:
        return None
    if label:
        return next((r for r in regs if r.label == label), None)
    return regs[0]


def _engine():
    # Default-region engine (READ-ONLY) — used by the dashboard when no region is given.
    r = resolve_region(None)
    if r is None:
        raise RuntimeError("no chat DB region configured (set REGIONS/REGION_*_CHAT_DB_URL or CHAT_DB_URL)")
    return _engine_for(r.url, r.db_name)


_EXPECTED_TABLES = ["conversations", "messages", "feedback", "token_usage"]
_PLATFORM_TABLES = ["threads", "thread_messages"]


_LAYOUT_CACHE: dict[str, bool] = {}  # (db url + schema) → is-platform-schema; layout is static


def _platform_layout(connection, schema: str) -> bool:
    """Whether the schema uses the platform (threads) layout. Cached per db+schema — the layout
    never changes for the life of the process, so this saves a round-trip on every dashboard call."""
    key = f"{connection.engine.url}|{schema}"
    cached = _LAYOUT_CACHE.get(key)
    if cached is not None:
        return cached
    result = bool(connection.execute(
        text("select to_regclass(:relation) is not null"),
        {"relation": f"{schema}.threads"},
    ).scalar_one())
    _LAYOUT_CACHE[key] = result
    return result


def region_labels(env: str = "uit") -> list[str]:
    return [r.label for r in configured_regions(env)]


def check_regions(env: str = "uit") -> list[dict]:
    """Test every configured region (READ-ONLY): connect + count the required tables.
    Never raises — returns a per-region status so startup can log/continue."""
    out: list[dict] = []
    for r in configured_regions(env):
        u = make_url(r.url)
        info: dict = {
            "env": env, "label": r.label, "host": u.host, "db": r.db_name, "schema": r.schema,
            "ok": False, "error": None, "counts": {},
        }
        try:
            sch = safe_schema(r.schema)
            eng = _engine_for(r.url, r.db_name)
            try:
                with eng.connect() as c:
                    tables = _PLATFORM_TABLES if _platform_layout(c, sch) else _EXPECTED_TABLES
                    for t in tables:
                        info["counts"][t] = c.execute(
                            text(f'select count(*) from "{sch}".{t}')
                        ).scalar_one()
                info["ok"] = True
            finally:
                eng.dispose()
        except Exception as ex:  # connection / permission / missing table
            info["error"] = f"{type(ex).__name__}: {str(ex)[:160]}"
        out.append(info)
    return out


def load_one_from_chatdb(conversation_id: str, engine=None, env: str = "uit") -> Conversation | None:
    """Load a single conversation by id, across all regions of an env (for on-demand analyse)."""
    convs = load_from_chatdb(engine=engine, ids=[conversation_id], env=env)
    return convs[0] if convs else None


def _eligible_in_region(
    region: RegionConfig, engine, limit: int | None, feedback_only: bool = False
) -> list[str]:
    """Eligible conversation ids in one region. When `feedback_only` (PROD posture), restrict to
    conversations that carry explicit user feedback — PROD has far too many conversations to
    bulk-analyse, so the sweep only touches the ones a customer reacted to (others are analysed
    one-by-one via the per-conversation button)."""
    sch = safe_schema(region.schema)
    eng = engine or _engine_for(region.url, region.db_name)
    try:
        with eng.connect() as c:
            if _platform_layout(c, sch):
                if feedback_only:
                    # Feedback location isn't known for the platform schema → nothing bulk-eligible.
                    return []
                # Only threads that actually have messages — a message-less thread has no
                # transcript to analyse and would otherwise be labelled from an empty prompt.
                sql = (
                    f"select id from \"{sch}\".threads "
                    f"where updated_at < now() - interval '5 minutes' "
                    f"and exists (select 1 from \"{sch}\".thread_messages tm where tm.thread_id = threads.id) "
                    f"order by updated_at desc"
                )
            else:
                # Skip conversations with no rows in `messages` (empty/purged) — nothing to analyse.
                feedback = (
                    f"and exists (select 1 from \"{sch}\".messages m join \"{sch}\".feedback f "
                    f"on f.message_id = m.id where m.conversation_id = conversations.id) "
                    if feedback_only else
                    f"and exists (select 1 from \"{sch}\".messages m where m.conversation_id = conversations.id) "
                )
                sql = (
                    f"select id from \"{sch}\".conversations "
                    f"where is_deleted = false "
                    f"and (last_message_at is null or last_message_at < now() - interval '5 minutes') "
                    f"{feedback}"
                    f"order by last_message_at desc nulls last"
                )
            if limit:
                sql += " limit :lim"
            rows = c.execute(text(sql), {"lim": limit} if limit else {}).all()
        return [str(r[0]) for r in rows]
    finally:
        if engine is None:
            eng.dispose()


def eligible_conversation_ids(limit: int | None = None, engine=None) -> list[str]:
    """Eligible IDs (not deleted, inactive >= 5 min) across ALL configured regions.
    A region that errors (e.g. permission denied) is skipped so it can't block the others."""
    if engine is not None:
        return _eligible_in_region(_primary_region(), engine, limit)
    out: list[str] = []
    for region in configured_regions():
        try:
            out += _eligible_in_region(region, None, limit)
        except Exception as ex:  # noqa: BLE001 - one bad region must not stop the rest
            print(f"[warn] eligibility skipped region '{region.label}': {type(ex).__name__}", flush=True)
    return out


def load_from_chatdb(
    limit: int | None = None, engine=None, ids: list[str] | None = None, env: str = "uit"
) -> list[Conversation]:
    """Load conversations across ALL configured regions of an env (each tagged region+env)."""
    if engine is not None:  # explicit engine → single region (tests / dashboard helpers)
        return _load_region(_primary_region(), limit=limit, ids=ids, engine=engine, env=env)
    out: list[Conversation] = []
    for region in configured_regions(env):
        try:
            out += _load_region(region, limit=limit, ids=ids, env=env)
        except Exception as ex:  # noqa: BLE001 - skip an unreachable region, keep the rest
            print(f"[warn] load skipped region '{region.label}': {type(ex).__name__}", flush=True)
    return out


def _load_platform_region(
    region: RegionConfig, limit: int, engine, ids: list[str] | None = None, env: str = "uit"
) -> list[Conversation]:
    sch = safe_schema(region.schema)
    with engine.connect() as c:
        if ids is not None:
            threads = c.execute(
                text(
                    f'select id, tenant_id, user_id, title, created_at from "{sch}".threads '
                    f'where id::text in :ids'
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids},
            ).mappings().all()
        else:
            threads = c.execute(
                text(
                    f'select id, tenant_id, user_id, title, created_at from "{sch}".threads '
                    f'order by updated_at desc limit :limit'
                ),
                {"limit": limit},
            ).mappings().all()
        thread_ids = [str(row["id"]) for row in threads]
        if not thread_ids:
            return []
        messages = c.execute(
            text(
                f'select id, thread_id, role, content, model, tokens, latency_ms, created_at, '
                f'row_number() over (partition by thread_id order by created_at, id) sequence_num '
                f'from "{sch}".thread_messages where thread_id::text in :ids '
                f'order by thread_id, created_at, id'
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": thread_ids},
        ).mappings().all()

    messages_by_thread: dict[str, list[Message]] = defaultdict(list)
    for row in messages:
        role = row["role"] if row["role"] in {"system", "user", "assistant", "live_agent"} else "assistant"
        # Platform schema stores a single `tokens` total (not split) + `latency_ms`. Map to the
        # closest Message fields so telemetry isn't lost: assistant token total -> output_tokens,
        # user token total -> input_tokens, latency -> ttft_ms. (NOTE: platform feedback is not
        # available in thread_messages, so Feedback stays empty here.)
        tokens = row["tokens"]
        latency = row["latency_ms"]
        is_assistant = role in {"assistant", "live_agent"}
        messages_by_thread[str(row["thread_id"])].append(
            Message(
                id=str(row["id"]),
                role=role,
                content=row["content"] or "",
                sequence_num=int(row["sequence_num"]),
                status="completed",
                model=row["model"],
                created_at=str(row["created_at"]) if row["created_at"] else "",
                input_tokens=int(tokens) if (tokens is not None and not is_assistant) else None,
                output_tokens=int(tokens) if (tokens is not None and is_assistant) else None,
                ttft_ms=int(latency) if latency is not None else None,
            )
        )
    return [
        Conversation(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"] or ""),
            title=row["title"],
            created_at=str(row["created_at"]) if row["created_at"] else "",
            messages=messages_by_thread.get(str(row["id"]), []),
            feedback=Feedback(),
            region=region.label,
            environment=env,
        )
        for row in threads
    ]


def _load_region(
    region: RegionConfig, limit: int | None = None, engine=None, ids: list[str] | None = None,
    env: str = "uit",
) -> list[Conversation]:
    limit = limit or settings.chatdb_limit
    sch = safe_schema(region.schema)
    eng = engine or _engine_for(region.url, region.db_name)
    try:
        with eng.connect() as c:
            platform = _platform_layout(c, sch)
        if platform:
            return _load_platform_region(region, limit, eng, ids, env=env)
        with eng.connect() as c:
            if ids is not None:
                convs = c.execute(
                    text(
                        f'select id, tenant_id, user_id, title, created_at, last_message_at '
                        f'from "{sch}".conversations '
                        f'where is_deleted = false and id::text in :cids'
                    ).bindparams(bindparam("cids", expanding=True)),
                    {"cids": ids},
                ).mappings().all()
            else:
                convs = c.execute(
                    text(
                        f'select id, tenant_id, user_id, title, created_at, last_message_at '
                        f'from "{sch}".conversations '
                        f'where is_deleted = false '
                        f'order by last_message_at desc nulls last limit :lim'
                    ),
                    {"lim": limit},
                ).mappings().all()
            ids = [str(r["id"]) for r in convs]
            if not ids:
                return []

            msgs = c.execute(
                text(
                    f'select id, conversation_id, role, content, input_tokens, output_tokens, '
                    f'total_tokens, model, latency, status, error_message, sequence_num, created_at '
                    f'from "{sch}".messages where conversation_id::text in :ids '
                    f'order by conversation_id, sequence_num'
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids},
            ).mappings().all()
            mids = [str(m["id"]) for m in msgs]

            feedback = (
                c.execute(
                    text(
                        f'select message_id, rating, comment from "{sch}".feedback '
                        f'where message_id::text in :mids'
                    ).bindparams(bindparam("mids", expanding=True)),
                    {"mids": mids},
                ).mappings().all()
                if mids
                else []
            )
            usage = (
                c.execute(
                    text(
                        f'select message_id, total_input_tokens, total_output_tokens, elapsed_seconds '
                        f'from "{sch}".token_usage where message_id::text in :mids'
                    ).bindparams(bindparam("mids", expanding=True)),
                    {"mids": mids},
                ).mappings().all()
                if mids
                else []
            )
    finally:
        if engine is None:
            eng.dispose()

    msgs_by_conv: dict[str, list] = defaultdict(list)
    for m in msgs:
        msgs_by_conv[str(m["conversation_id"])].append(m)
    fb_by_msg = {str(f["message_id"]): f for f in feedback}
    usage_by_msg = {str(u["message_id"]): u for u in usage}

    conversations: list[Conversation] = []
    for r in convs:
        cid = str(r["id"])
        rows = msgs_by_conv.get(cid, [])
        messages: list[Message] = []
        conv_feedback = Feedback()
        for m in rows:
            mid = str(m["id"])
            u = usage_by_msg.get(mid)
            messages.append(
                Message(
                    id=mid,
                    role=m["role"] or "assistant",
                    content=m["content"] or "",
                    sequence_num=m["sequence_num"] if m["sequence_num"] is not None else len(messages) + 1,
                    status=m["status"],
                    error_message=m["error_message"],
                    model=m["model"],
                    created_at=str(m["created_at"]) if m["created_at"] else "",
                    # authoritative tokens from token_usage when present, else the message row
                    input_tokens=(u["total_input_tokens"] if u else None) or m["input_tokens"],
                    output_tokens=(u["total_output_tokens"] if u else None) or m["output_tokens"],
                    prompt_tokens=(u["total_input_tokens"] if u else None) or m["input_tokens"],
                    # Chat DB has no true TTFT; use real response latency (elapsed_seconds→ms)
                    # from token_usage, else the message latency column; else unavailable (AC-7).
                    ttft_ms=(
                        int(u["elapsed_seconds"] * 1000)
                        if u and u.get("elapsed_seconds") is not None
                        else m["latency"]
                    ),
                )
            )
            fb = fb_by_msg.get(mid)
            if fb and conv_feedback.rating is None:
                conv_feedback = Feedback(rating=fb["rating"], comment=fb["comment"], message_id=mid)

        conversations.append(
            Conversation(
                id=cid,
                tenant_id=str(r["tenant_id"]) if r["tenant_id"] is not None else "",
                title=r["title"],
                created_at=str(r["created_at"]) if r["created_at"] else "",
                messages=messages,
                feedback=conv_feedback,
                region=region.label,  # tag the source region → flows into the analysis record
                environment=env,  # tag the source environment → strict isolation in the store
            )
        )
    return conversations
