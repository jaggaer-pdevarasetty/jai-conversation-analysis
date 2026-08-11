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

import re
from collections import defaultdict

from sqlalchemy import bindparam, create_engine, text

from .config import settings
from .domain.models import Conversation, Feedback, Message

_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


def safe_schema() -> str:
    """Whitelist the schema NAME (it's interpolated into SQL; values use bound params)."""
    sch = settings.chat_db_schema
    if not _IDENT.match(sch):
        raise ValueError(f"invalid CHAT_DB_SCHEMA: {sch!r}")
    return sch


def _engine():
    # READ-ONLY use; connect to the real DB (chat_db_name) regardless of the URL's db part.
    from sqlalchemy.engine import make_url

    url = make_url(settings.chat_db_url).set(database=settings.chat_db_name)
    return create_engine(url, connect_args={"connect_timeout": 15})


def load_one_from_chatdb(conversation_id: str, engine=None) -> Conversation | None:
    """Load a single conversation by id (for on-demand analyse)."""
    convs = load_from_chatdb(engine=engine, ids=[conversation_id])
    return convs[0] if convs else None


def eligible_conversation_ids(limit: int | None = None, engine=None) -> list[str]:
    """IDs of conversations eligible for analysis: not deleted and inactive >= 5 minutes.
    (Eligibility is enforced in the DB so we don't pull transcripts just to skip them.)"""
    sch = safe_schema()
    eng = engine or _engine()
    try:
        with eng.connect() as c:
            sql = (
                f"select id from \"{sch}\".conversations "
                f"where is_deleted = false "
                f"and (last_message_at is null or last_message_at < now() - interval '5 minutes') "
                f"order by last_message_at desc nulls last"
            )
            if limit:
                sql += " limit :lim"
            rows = c.execute(text(sql), {"lim": limit} if limit else {}).all()
        return [str(r[0]) for r in rows]
    finally:
        if engine is None:
            eng.dispose()


def load_from_chatdb(
    limit: int | None = None, engine=None, ids: list[str] | None = None
) -> list[Conversation]:
    limit = limit or settings.chatdb_limit
    sch = safe_schema()
    eng = engine or _engine()
    try:
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
                conv_feedback = Feedback(rating=fb["rating"], comment=fb["comment"])

        conversations.append(
            Conversation(
                id=cid,
                tenant_id=str(r["tenant_id"]) if r["tenant_id"] is not None else "",
                title=r["title"],
                created_at=str(r["created_at"]) if r["created_at"] else "",
                messages=messages,
                feedback=conv_feedback,
            )
        )
    return conversations
