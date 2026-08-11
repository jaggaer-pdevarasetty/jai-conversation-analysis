"""FastAPI read API for the pooled, de-identified common analysis area (J1-93353).

Attribution (ADR-0007): everything is keyed by conversation_id; no tenant/user is exposed.
RBAC: reviewer-only (gate configurable). RFC 7807 error bodies.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .domain.models import CATEGORIES, AnalysisRecord, CommonConversation, Conversation
from .gemini import make_batch_analyzer
from .problem import problem_response
from .run import run_analysis
from .sources import load_conversations
from .store_factory import make_store

app = FastAPI(title="JAI Conversation Analysis API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    # Dev: allow the reviewer UI from any localhost/127.0.0.1 port (incl. browser previews).
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _load_source() -> list[Conversation]:
    """Load conversations from the configured source; never crash startup on a source error."""
    try:
        return load_conversations()
    except Exception as exc:  # noqa: BLE001 - surface, don't crash
        print(f"[warn] source '{settings.source}' load failed: {type(exc).__name__}", flush=True)
        return []


# Common store (memory by default; Postgres when STORE_BACKEND=sql). Seeded by one analysis
# run over the configured source (fixtures | langsmith). In production a scheduler triggers
# run_analysis every 4h; classification uses Vertex when configured, else deterministic rules.
store = make_store()
latest_run = run_analysis(store, _load_source(), analyze_batch=make_batch_analyzer())


def require_reviewer(x_roles: str | None = Header(default=None)) -> None:
    """RBAC gate for the pooled area (reviewers only). No-op when RBAC is disabled (dev/tests)."""
    if not settings.rbac_enabled:
        return
    roles = {r.strip().lower() for r in (x_roles or "").split(",")}
    if "reviewer" not in roles:
        raise HTTPException(status_code=403, detail="Reviewer role required")


def _metrics(record: AnalysisRecord) -> dict:
    return asdict(record.metrics)  # None values → JSON null (AC-7: unavailable, not zero)


def _list_item(record: AnalysisRecord, conv: CommonConversation | None) -> dict:
    return {
        "conversation_id": record.conversation_id,
        "category": record.category,
        "model_category": record.model_category,
        "recommended_next_step": record.recommended_next_step,
        "confidence": record.confidence,
        "status": record.status,
        "overridden": record.override is not None,
        "has_feedback": bool(conv and conv.feedback.rating is not None),
        "metrics": _metrics(record),
        "analyzed_at": record.analyzed_at,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api = APIRouter(prefix="/api/analysis", dependencies=[Depends(require_reviewer)])


@api.get("/conversations")
def list_conversations(
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if category is not None and category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {category}")
    records = store.list(category=category)  # type: ignore[arg-type]
    page = records[offset : offset + limit]
    items = [_list_item(r, store.get_conversation(r.conversation_id)) for r in page]
    return {
        "items": items,
        "counts": store.count_by_category(),
        "total": len(records),
        "unanalysed": store.unanalysed_count(),
        "limit": limit,
        "offset": offset,
    }


def _conversation_detail(conversation_id: str) -> dict | None:
    record = store.get_analysis(conversation_id)
    conv = store.get_conversation(conversation_id)
    if record is None or conv is None:
        return None
    return {
        "conversation_id": conversation_id,
        "analysis": {
            "category": record.category,
            "model_category": record.model_category,
            "recommended_next_step": record.recommended_next_step,
            "confidence": record.confidence,
            "rationale": record.rationale,
            "signals": asdict(record.signals),
            "status": record.status,
            "override": asdict(record.override) if record.override else None,
            "run_id": record.run_id,
            "analyzer_version": record.analyzer_version,
            "analyzed_at": record.analyzed_at,
        },
        "metrics": _metrics(record),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sequence_num": m.sequence_num,
                "model": m.model,
                "created_at": m.created_at,
            }
            for m in conv.messages
        ],
        "feedback": {"rating": conv.feedback.rating, "comment": conv.feedback.comment},
    }


@api.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    payload = _conversation_detail(conversation_id)
    if payload is None:
        return problem_response(404, "Not found", f"No analysis for conversation {conversation_id}")
    return payload


@api.post("/conversations/{conversation_id}/analyze")
def analyze_conversation(conversation_id: str):
    """On-demand (re)analyse ONE conversation now. Capped at MAX_ANALYSES_PER_DAY per convo."""
    import uuid
    from datetime import datetime, timezone

    from .chatdb import load_one_from_chatdb
    from .deidentify import deidentify

    if store.analyses_today(conversation_id) >= settings.max_analyses_per_day:
        return problem_response(
            429, "Daily analyse limit reached",
            f"This conversation was already analysed {settings.max_analyses_per_day} times today.",
        )
    try:
        conv = load_one_from_chatdb(conversation_id)
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)
    if conv is None:
        return problem_response(404, "Not found", f"No source conversation {conversation_id}")

    now = datetime.now(timezone.utc)
    records = make_batch_analyzer()([conv], f"ondemand_{uuid.uuid4().hex[:8]}", now.isoformat())
    if not records:
        store.mark_failed(conversation_id)
        return problem_response(503, "Analysis failed", "model unavailable; please retry")
    store.record_analysis(conversation_id, now.isoformat())
    store.upsert(records[0], deidentify(conv))
    return _conversation_detail(conversation_id)


class OverrideBody(BaseModel):
    category: str
    actor: str


@api.post("/conversations/{conversation_id}/override")
def override_category(conversation_id: str, body: OverrideBody):
    if body.category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {body.category}")
    record = store.set_override(conversation_id, body.category, body.actor)  # type: ignore[arg-type]
    if record is None:
        return problem_response(404, "Not found", f"No analysis for conversation {conversation_id}")
    return {
        "conversation_id": record.conversation_id,
        "category": record.category,
        "model_category": record.model_category,
        "recommended_next_step": record.recommended_next_step,
        "override": asdict(record.override) if record.override else None,
    }


@api.get("/runs/latest")
def latest_run_summary():
    return asdict(latest_run) | {"unanalysed": latest_run.unanalysed}


# ── Admin dashboard: tenant → user → conversation drill-down (authorised view) ──
@api.get("/dashboard/overview")
def dashboard_overview():
    from . import dashboard

    try:
        return dashboard.overview(store)
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


@api.get("/dashboard/tenants")
def dashboard_tenants():
    from . import dashboard

    try:
        return {"items": dashboard.tenants()}
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


@api.get("/dashboard/tenants/{tenant_id}/users")
def dashboard_users(tenant_id: str):
    from . import dashboard

    try:
        return {"items": dashboard.users(tenant_id)}
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


def _lazy_analyze(conversation_ids: list[str]) -> None:
    """Background: analyse a user's un-analysed conversations in CHUNKS, clearing 'analysing'
    per conversation as each chunk finishes so the UI updates incrementally."""
    import uuid
    from datetime import datetime, timezone

    from .chatdb import load_from_chatdb
    from .deidentify import deidentify

    now = datetime.now(timezone.utc).isoformat()
    analyzer = make_batch_analyzer()
    try:
        convs = load_from_chatdb(ids=conversation_ids)
    except Exception as exc:  # noqa: BLE001 - never crash a background task
        print(f"[warn] lazy analyse load failed: {type(exc).__name__}", flush=True)
        for cid in conversation_ids:
            store.clear_analyzing(cid)
        return

    size = max(1, settings.batch_size)
    for i in range(0, len(convs), size):
        chunk = convs[i : i + size]
        try:
            records = {r.conversation_id: r for r in analyzer(chunk, f"lazy_{uuid.uuid4().hex[:8]}", now)}
        except Exception:  # noqa: BLE001
            records = {}
        for conv in chunk:
            rec = records.get(conv.id)
            if rec is not None:
                store.upsert(rec, deidentify(conv))
                store.record_analysis(conv.id, now)
            else:
                store.mark_failed(conv.id)
            store.clear_analyzing(conv.id)  # incremental: this one is done now

    loaded = {c.id for c in convs}
    for cid in conversation_ids:  # ids that no longer exist → don't leave them 'analysing'
        if cid not in loaded:
            store.clear_analyzing(cid)


@api.get("/dashboard/tenants/{tenant_id}/users/{user_id}/conversations")
def dashboard_user_conversations(tenant_id: str, user_id: str, background_tasks: BackgroundTasks):
    from . import dashboard

    try:
        items = dashboard.user_conversations(store, tenant_id, user_id)
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)

    # Lazy analyse: kick off un-analysed ones in the background and mark them 'analysing'.
    pending = [it["conversation_id"] for it in items if it["status"] == "pending"]
    if settings.lazy_analyze and pending:
        store.mark_analyzing(pending)
        background_tasks.add_task(_lazy_analyze, pending)
        for it in items:
            if it["conversation_id"] in pending:
                it["status"] = "analysing"
    return {"items": items}


@api.post("/runs")
def trigger_run():
    """Trigger a run (scheduler / reviewer). Re-analyses eligible, not-yet-analysed convs."""
    global latest_run
    latest_run = run_analysis(store, _load_source(), analyze_batch=make_batch_analyzer())
    return asdict(latest_run) | {"unanalysed": latest_run.unanalysed}


app.include_router(api)
