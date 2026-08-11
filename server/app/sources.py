"""Conversation sources (ADR-0012).

- fixtures: built-in samples (default).
- langsmith: real conversations reconstructed from LangSmith runs (uses the env-aware HTTP
  client so it works behind Zscaler via REQUESTS_CA_BUNDLE + HTTPS_PROXY).

The run→conversation field mapping is best-effort and isolated in small helpers; it must be
validated against one real LangSmith sample (the chat DB is the canonical transcript — this
gives us conversation_id + authoritative tokens/latency + intent/frustration signals).
tenant_id is carried on the SOURCE side only and dropped by de-identification (ADR-0007)
before anything reaches the common store.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import httpx

from .config import settings
from .domain.models import Conversation, Feedback, Message
from .fixtures import CONVERSATIONS
from .http import client as make_client


def _text(val: Any) -> str:
    """Best-effort extraction of message text from LangSmith inputs/outputs."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return _text(val[-1]) if val else ""
    if isinstance(val, dict):
        for key in ("content", "text", "output", "input", "messages", "output_text"):
            if key in val:
                return _text(val[key])
        return ""
    return str(val)


def _metadata(run: dict) -> dict:
    return (run.get("extra") or {}).get("metadata") or {}


def _iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _ttft_ms(run: dict) -> int | None:
    start, first = run.get("start_time"), run.get("first_token_time")
    if not start or not first:
        return None
    return int((_iso(first) - _iso(start)).total_seconds() * 1000)


def runs_to_conversations(runs: list[dict]) -> list[Conversation]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        md = _metadata(run)
        cid = md.get("conversation_id") or md.get("thread_id") or run.get("id")
        grouped[str(cid)].append(run)

    conversations: list[Conversation] = []
    for cid, group in grouped.items():
        group.sort(key=lambda r: r.get("start_time") or "")
        messages: list[Message] = []
        seq = 0
        for run in group:
            user_text = _text(run.get("inputs"))
            if user_text:
                seq += 1
                messages.append(
                    Message(id=f"{run.get('id')}-u", role="user", content=user_text,
                            sequence_num=seq, created_at=run.get("start_time") or "")
                )
            asst_text = _text(run.get("outputs"))
            if asst_text:
                seq += 1
                messages.append(
                    Message(
                        id=f"{run.get('id')}-a", role="assistant", content=asst_text,
                        sequence_num=seq,
                        created_at=run.get("end_time") or run.get("start_time") or "",
                        model=_metadata(run).get("ls_model_name") or run.get("name"),
                        input_tokens=run.get("prompt_tokens"),
                        output_tokens=run.get("completion_tokens"),
                        prompt_tokens=run.get("prompt_tokens"),
                        ttft_ms=_ttft_ms(run),
                    )
                )
        last = _metadata(group[-1])
        conversations.append(
            Conversation(
                id=cid,
                tenant_id=str(last.get("tenant_id", "")),  # dropped by de-identify() later
                title=None,
                created_at=group[0].get("start_time") or "",
                messages=messages,
                feedback=Feedback(),
                out_of_scope_intent=bool(last.get("out_of_scope_intent") or last.get("intent") == "out_of_scope"),
                frustrated=bool(last.get("frustrated")),
            )
        )
    return conversations


def _resolve_session_id(hc: httpx.Client, base: str, project: str, headers: dict) -> str:
    resp = hc.get(f"{base}/api/v1/sessions", params={"name": project}, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    sessions = data if isinstance(data, list) else data.get("sessions", [])
    if not sessions:
        raise RuntimeError(f"LangSmith project not found: {project}")
    return sessions[0]["id"]


def _query_runs(hc: httpx.Client, base: str, session_id: str, limit: int, headers: dict) -> list[dict]:
    resp = hc.post(
        f"{base}/api/v1/runs/query",
        headers=headers,
        json={"session": [session_id], "limit": limit},
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("runs", data if isinstance(data, list) else [])


def load_from_langsmith(limit: int | None = None, http_client: httpx.Client | None = None) -> list[Conversation]:
    headers = {"x-api-key": settings.langsmith_api_key} if settings.langsmith_api_key else {}
    base = settings.langsmith_base_url.rstrip("/")
    hc = http_client or make_client(timeout=30.0)
    try:
        session_id = _resolve_session_id(hc, base, settings.langsmith_project, headers)
        runs = _query_runs(hc, base, session_id, limit or settings.langsmith_limit, headers)
    finally:
        if http_client is None:
            hc.close()
    return runs_to_conversations(runs)


def load_conversations() -> list[Conversation]:
    if settings.source == "langsmith":
        return load_from_langsmith()
    return CONVERSATIONS
