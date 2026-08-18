"""FastAPI read API for the pooled, de-identified common analysis area (J1-93353).

Attribution (ADR-0007): everything is keyed by conversation_id; no tenant/user is exposed.
RBAC: reviewer-only (gate configurable). RFC 7807 error bodies.
"""

from __future__ import annotations

import threading
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Response
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


# Common store (memory by default; Postgres when STORE_BACKEND=sql).
store = make_store()

# Analysis queue: bounded, deduped, worker-pooled (never re-runs/loops). Used by lazy analyse
# and (at startup, chatdb) to give FULL coverage in the background without blocking boot.
from .queue import AnalysisQueue  # noqa: E402

analysis_queue = AnalysisQueue(store, make_batch_analyzer(), workers=settings.queue_workers)

def _eligible_by_region(region: str | None = None) -> dict[str, list[str]]:
    """{region_label: eligible ids}. One region if given, else all configured. A region that
    errors (e.g. permission denied) is skipped so it can't block the others."""
    from .chatdb import _eligible_in_region, configured_regions, resolve_region

    regions = [resolve_region(region)] if region else configured_regions()
    out: dict[str, list[str]] = {}
    for r in regions:
        if r is None:
            continue
        try:
            out[r.label] = _eligible_in_region(r, None, None)
        except Exception as exc:  # noqa: BLE001 - one bad region must not stop the rest
            print(f"[warn] eligibility skipped region '{r.label}': {type(exc).__name__}", flush=True)
            out[r.label] = []
    return out


def _sweep(region: str | None = None) -> None:
    """Enqueue every eligible, not-yet-analysed conversation (deduped by the queue). Limited to
    `region` when given, else all configured regions. Pre-filters with a single analysed_ids()
    query so we don't fire one is_analysed() round-trip per eligible id on every trigger."""
    analysed = store.analysed_ids()
    ids = [cid for ids in _eligible_by_region(region).values() for cid in ids if cid not in analysed]
    analysis_queue.enqueue(ids)


_sweep_lock = threading.Lock()
_sweep_running = False


def trigger_sweep(region: str | None = None) -> bool:
    """Manual trigger: run a check + analyse sweep in the background (deduped; only
    not-yet-analysed conversations are processed) for `region` (or all). Returns False if a
    sweep is already running, so repeated button clicks don't pile up."""
    global _sweep_running
    with _sweep_lock:
        if _sweep_running:
            return False
        _sweep_running = True

    def _run() -> None:
        global _sweep_running
        try:
            _sweep(region)
        except Exception as exc:  # noqa: BLE001 - chat DB may be unreachable; never crash
            print(f"[warn] manual sweep failed: {type(exc).__name__}", flush=True)
        finally:
            with _sweep_lock:
                _sweep_running = False

    threading.Thread(target=_run, name="manual-sweep", daemon=True).start()
    return True


region_health: list[dict] = []  # per-region connectivity, checked once at startup
if settings.source == "chatdb":
    # Test EVERY configured region before serving: connect + verify the required tables.
    # We log and continue (a bad/permission-denied region must not crash the app or leak data).
    from .chatdb import check_regions

    region_health = check_regions()
    for h in region_health:
        state = "OK " + str(h["counts"]) if h["ok"] else f"UNREACHABLE ({h['error']})"
        print(f"[startup] region '{h['label']}' {h['host']}/{h['db']}.{h['schema']}: {state}", flush=True)
    if not any(h["ok"] for h in region_health):
        print("[startup][warn] NO region is readable — dashboards will be empty until fixed.", flush=True)

    # MANUAL mode: workers are ready, but analysis runs ONLY when triggered from the UI
    # (POST /analyze/sweep). No boot sweep and no scheduled cadence.
    analysis_queue.start()
    latest_run = run_analysis(store, [], analyze_batch=make_batch_analyzer())  # empty summary
else:
    # fixtures / langsmith: seed synchronously so the pooled list is populated immediately.
    latest_run = run_analysis(store, _load_source(), analyze_batch=make_batch_analyzer())


def require_reviewer(x_roles: str | None = Header(default=None)) -> None:
    """RBAC gate for the pooled area (reviewers only). No-op when RBAC is disabled (dev/tests)."""
    if not settings.rbac_enabled:
        return
    roles = {r.strip().lower() for r in (x_roles or "").split(",")}
    if "reviewer" not in roles:
        raise HTTPException(status_code=403, detail="Reviewer role required")


def _bad_region(region: str | None):
    """Reject an unknown region label (strict — prevents accidental cross-region leakage)."""
    if region is None:
        return None
    from .chatdb import region_labels

    if region not in region_labels():
        return problem_response(400, "Invalid region", f"Unknown region: {region}")
    return None


def _metrics(record: AnalysisRecord) -> dict:
    return asdict(record.metrics)  # None values → JSON null (AC-7: unavailable, not zero)


def _last_message_at(conv: CommonConversation | None) -> str | None:
    if conv is None:
        return None
    value = max((message.created_at for message in conv.messages if message.created_at), default=None)
    return value.replace(" ", "T", 1) if value else None


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
        "last_message_at": _last_message_at(conv),
        "analyzed_at": record.analyzed_at,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api = APIRouter(prefix="/api/analysis", dependencies=[Depends(require_reviewer)])


@api.get("/regions")
def list_regions():
    """Regions available for the UI dropdown, with startup reachability + table counts."""
    from .chatdb import configured_regions

    health = {h["label"]: h for h in region_health}
    return {
        "items": [
            {
                "label": r.label,
                "reachable": health.get(r.label, {}).get("ok"),
                "counts": health.get(r.label, {}).get("counts", {}),
                "error": health.get(r.label, {}).get("error"),
            }
            for r in configured_regions()
        ]
    }


@api.get("/conversations")
def list_conversations(
    category: str | None = Query(default=None),
    region: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    confidence: str | None = Query(default=None),
    review_state: str | None = Query(default=None),
    sort: str = Query(default="newest"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if category is not None and category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {category}")
    if (bad := _bad_region(region)) is not None:
        return bad
    if confidence is not None and confidence not in {"high", "medium", "low"}:
        return problem_response(400, "Invalid confidence", f"Unknown confidence: {confidence}")
    if review_state is not None and review_state not in {"attention", "feedback", "overridden", "missing_telemetry"}:
        return problem_response(400, "Invalid review state", f"Unknown review state: {review_state}")
    if sort not in {"newest", "oldest", "attention", "confidence", "slowest", "tokens"}:
        return problem_response(400, "Invalid sort", f"Unknown sort: {sort}")

    records = store.list(category=category, region=region)  # type: ignore[arg-type]
    conversations = store.get_conversations([record.conversation_id for record in records])
    items = [_list_item(record, conversations.get(record.conversation_id)) for record in records]
    text_query = (query or "").strip().lower()
    if text_query:
        items = [
            item for item in items
            if text_query in item["conversation_id"].lower()
            or text_query in item["recommended_next_step"].lower()
        ]
    if confidence:
        items = [item for item in items if item["confidence"] == confidence]
    if review_state == "attention":
        items = [item for item in items if item["category"] in {"failed_to_resolve", "negative_feedback", "out_of_scope"}]
    elif review_state == "feedback":
        items = [item for item in items if item["has_feedback"]]
    elif review_state == "overridden":
        items = [item for item in items if item["overridden"]]
    elif review_state == "missing_telemetry":
        items = [
            item for item in items
            if item["metrics"]["ttft_ms"] is None
            or item["metrics"]["input_tokens"] is None
            or item["metrics"]["output_tokens"] is None
        ]

    priority = {"negative_feedback": 0, "failed_to_resolve": 1, "out_of_scope": 2, "positive_feedback": 3, "resolved": 4}
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    if sort == "newest":
        items.sort(key=lambda item: item.get("last_message_at") or item.get("analyzed_at") or "", reverse=True)
    elif sort == "oldest":
        items.sort(key=lambda item: item.get("last_message_at") or item.get("analyzed_at") or "")
    elif sort == "confidence":
        items.sort(key=lambda item: confidence_order.get(item["confidence"], 3))
    elif sort == "slowest":
        items.sort(key=lambda item: item["metrics"]["ttft_ms"] or -1, reverse=True)
    elif sort == "tokens":
        items.sort(key=lambda item: (item["metrics"]["input_tokens"] or 0) + (item["metrics"]["output_tokens"] or 0), reverse=True)
    else:
        items.sort(key=lambda item: priority.get(item["category"], 9))

    total = len(items)
    return {
        "items": items[offset : offset + limit],
        "counts": store.count_by_category(region=region),
        "total": total,
        "unanalysed": store.unanalysed_count(),
        "region": region,
        "limit": limit,
        "offset": offset,
    }


def _conversation_detail(conversation_id: str) -> dict | None:
    record = store.get_analysis(conversation_id)
    conv = store.get_conversation(conversation_id)
    if record is None or conv is None:
        return None
    source = None
    try:
        from . import dashboard

        source = dashboard.conversation_meta([conversation_id]).get(conversation_id)
    except Exception:  # noqa: BLE001 - chat DB optional; detail still works de-identified
        source = None
    return {
        "conversation_id": conversation_id,
        "source": source,  # tenant/user/title/timestamps (authorised admin view)
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
        "deep": asdict(record.deep) if record.deep else None,
        "enrichment": asdict(record.enrichment) if record.enrichment else None,
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


_NEGATIVE_CATEGORIES = {"negative_feedback", "failed_to_resolve"}


@api.get("/feedback")
def feedback_conversations(
    scope: str = Query(default="thumbs", pattern="^(thumbs|outcomes|all)$"),
    region: str | None = Query(default=None),
    rating: str | None = Query(default=None, pattern="^(positive|negative)$"),
    category: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    tenant: str | None = Query(default=None, max_length=200),
    date_range: str | None = Query(default=None, pattern="^(last_7_days|last_30_days)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|oldest|negative_first)$"),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Feedback / negative-signal conversations, rich row per conversation for a reviewer table.

    scope=thumbs (default): only EXPLICIT thumbs feedback (up/down).
    scope=outcomes: conversations the model judged negative (failed_to_resolve /
        negative_feedback) even without a thumb — the large 'went badly' set.
    scope=all: union of both.
    """
    if (bad := _bad_region(region)) is not None:
        return bad
    if category is not None and category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {category}")
    if date_from and date_to and date_from > date_to:
        return problem_response(400, "Invalid date range", "date_from must be on or before date_to")
    items = []
    records = store.list(region=region)
    conversations = store.get_conversations([record.conversation_id for record in records])
    for record in records:
        conv = conversations.get(record.conversation_id)
        has_thumbs = conv is not None and conv.feedback.rating is not None
        neg_outcome = record.category in _NEGATIVE_CATEGORIES
        if scope == "thumbs" and not has_thumbs:
            continue
        if scope == "outcomes" and not neg_outcome:
            continue
        if scope == "all" and not (has_thumbs or neg_outcome):
            continue
        m = record.metrics
        deep = asdict(record.deep) if record.deep else None
        items.append(
            {
                "conversation_id": record.conversation_id,
                "category": record.category,
                "model_category": record.model_category,
                "confidence": record.confidence,
                "rating": conv.feedback.rating if conv else None,
                "comment": conv.feedback.comment if conv else None,
                "has_thumbs": has_thumbs,
                "recommended_next_step": record.recommended_next_step,
                "rationale": record.rationale,
                "why_it_happened": (deep or {}).get("why_it_happened", ""),
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "last_message_at": _last_message_at(conv),
                "analyzed_at": record.analyzed_at,
                "analyzer_version": record.analyzer_version,
                "deep": deep,
            }
        )

    scope_total = len(items)
    positive = sum(1 for item in items if item["rating"] is True)
    negative = sum(1 for item in items if item["rating"] is False)
    negative_outcomes = sum(1 for item in items if item["category"] in _NEGATIVE_CATEGORIES)
    deep_analysed = sum(1 for item in items if item["deep"])
    if rating:
        expected = rating == "positive"
        items = [item for item in items if item["rating"] is expected]
    if category:
        items = [item for item in items if item["category"] == category]

    # enrich with source metadata (tenant/user/title/timestamps) so the UI can show a table
    def _enrich(rows):
        try:
            from . import dashboard

            meta = dashboard.conversation_meta([item["conversation_id"] for item in rows], region=region)
        except Exception:  # noqa: BLE001 - chat DB optional
            meta = {}
        for item in rows:
            item.update(meta.get(item["conversation_id"], {}))

    text_query = (query or "").strip().lower()
    tenant_query = (tenant or "").strip().lower()
    needs_meta = bool(text_query or tenant_query or date_range or date_from or date_to)
    if needs_meta:
        _enrich(items)
    if text_query:
        items = [
            item for item in items
            if any(
                text_query in str(item.get(field) or "").lower()
                for field in (
                    "conversation_id", "comment", "title", "tenant_name", "user_name",
                    "recommended_next_step", "why_it_happened",
                )
            )
        ]
    if tenant_query:
        items = [item for item in items if tenant_query in str(item.get("tenant_name") or "").lower()]

    range_start = date_from
    range_end = date_to
    if date_range:
        range_end = datetime.now(timezone.utc).date()
        range_start = range_end - timedelta(days=6 if date_range == "last_7_days" else 29)
    if range_start or range_end:
        def _activity_day(item):
            value = item.get("last_message_at") or item.get("analyzed_at")
            if not value:
                return None
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except (ValueError, TypeError):
                return None  # legacy/odd timestamp → treat as undated (don't 500)

        items = [
            item for item in items
            if (day := _activity_day(item)) is not None
            and (range_start is None or day >= range_start)
            and (range_end is None or day <= range_end)
        ]

    def _rank(item) -> int:  # thumbs-down first, then negative outcomes, then thumbs-up, then rest
        if item["rating"] is False:
            return 0
        if item["category"] in _NEGATIVE_CATEGORIES:
            return 1
        if item["rating"] is True:
            return 2
        return 3

    if sort == "newest":
        items.sort(key=lambda item: item["last_message_at"] or item["analyzed_at"] or "", reverse=True)
    elif sort == "oldest":
        items.sort(key=lambda item: item["last_message_at"] or item["analyzed_at"] or "")
    else:
        items.sort(key=_rank)
    total = len(items)
    page = items[offset : offset + limit]
    if not needs_meta:
        _enrich(page)
    return {
        "items": page,
        "total": total,
        "scope_total": scope_total,
        "scope": scope,
        "positive": positive,
        "negative": negative,
        "negative_outcomes": negative_outcomes,
        "deep_analysed": deep_analysed,
        "limit": limit,
        "offset": offset,
    }


@api.get("/feedback/export")
def feedback_export(
    format: str = Query(default="csv", pattern="^(csv|json|pdf)$"),
    scope: str = Query(default="all", pattern="^(thumbs|outcomes|all)$"),
    region: str | None = Query(default=None),
    rating: str | None = Query(default=None, pattern="^(positive|negative)$"),
    category: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    tenant: str | None = Query(default=None, max_length=200),
    date_range: str | None = Query(default=None, pattern="^(last_7_days|last_30_days)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|oldest|negative_first)$"),
):
    """Download the feedback conversations for the current view (all matching rows, no
    pagination) with full detail — category, confidence, feedback + user remark, 3-part root
    cause, suggestions + recommended action, cost & responsiveness, and the full de-identified
    transcript — as CSV, JSON, or PDF. Honours the same filters as GET /feedback."""
    if (bad := _bad_region(region)) is not None:
        return bad
    if category is not None and category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {category}")
    if date_from and date_to and date_from > date_to:
        return problem_response(400, "Invalid date range", "date_from must be on or before date_to")
    from . import export

    rows = export.collect_rows(
        store, scope=scope, region=region, rating=rating, category=category,
        query=query, tenant=tenant, date_range=date_range,
        date_from=date_from, date_to=date_to, sort=sort,
    )
    data, media = export.render(rows, format)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ext = {"json": "json", "pdf": "pdf"}.get(format, "csv")
    filename = f"feedback-{scope}-{region or 'all'}-{stamp}.{ext}"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    if not conv.messages:  # empty conversation → nothing to analyse (avoid a hallucinated label)
        return problem_response(422, "No transcript", "This conversation has no messages to analyse.")

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
def dashboard_overview(region: str | None = Query(default=None)):
    from . import dashboard

    if (bad := _bad_region(region)) is not None:
        return bad
    try:
        return dashboard.overview(store, region=region)
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


def _pooled_block():
    from .privacy import is_pooled

    if is_pooled():
        return problem_response(
            403, "Pooled privacy mode", "Per-tenant drill-down is disabled in pooled mode (AC-10)."
        )
    return None


@api.get("/dashboard/tenants")
def dashboard_tenants(region: str | None = Query(default=None)):
    from . import dashboard

    if (blocked := _pooled_block()) is not None:
        return blocked
    if (bad := _bad_region(region)) is not None:
        return bad
    try:
        return {"items": dashboard.tenants(region=region), "region": region}
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


@api.get("/dashboard/tenants/{tenant_id}/users")
def dashboard_users(tenant_id: str, region: str | None = Query(default=None)):
    from . import dashboard

    if (blocked := _pooled_block()) is not None:
        return blocked
    if (bad := _bad_region(region)) is not None:
        return bad
    try:
        return {"items": dashboard.users(tenant_id, region=region), "region": region}
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


@api.get("/dashboard/tenants/{tenant_id}/users/{user_id}/conversations")
def dashboard_user_conversations(
    tenant_id: str,
    user_id: str,
    region: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from . import dashboard

    if (blocked := _pooled_block()) is not None:
        return blocked
    if (bad := _bad_region(region)) is not None:
        return bad
    try:
        items, total = dashboard.user_conversations(store, tenant_id, user_id, limit, offset, region=region)
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)

    # Lazy analyse: enqueue un-analysed ones (deduped, no re-run) and mark them 'analysing'.
    if settings.lazy_analyze:
        pending = [it["conversation_id"] for it in items if it["status"] == "pending"]
        accepted = set(analysis_queue.enqueue(pending)) if pending else set()
        for it in items:
            if it["conversation_id"] in accepted:
                it["status"] = "analysing"
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@api.get("/queue")
def queue_stats(
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Queue health: depth, in-flight, dead-letter, capacity, workers."""
    return analysis_queue.stats(limit=limit, offset=offset)


@api.get("/analyze/pending")
def analyze_pending(region: str | None = Query(default=None)):
    """Step 1 of the manual flow: FETCH (don't analyse) the eligible, not-yet-analysed
    conversations for the selected region (or all regions), returning the total, a per-region
    breakdown, and brief details for a sample. The UI then shows a 'Start analysis' button."""
    if settings.source != "chatdb":
        return {"count": 0, "ids": [], "by_region": {}, "items": [], "region": region, "source": settings.source}
    if (bad := _bad_region(region)) is not None:
        return bad
    from . import dashboard

    analysed = store.analysed_ids()
    by_ids = {lbl: [i for i in ids if i not in analysed] for lbl, ids in _eligible_by_region(region).items()}
    by_region = {lbl: len(ids) for lbl, ids in by_ids.items()}
    all_ids = [i for ids in by_ids.values() for i in ids]
    # Brief, privacy-aware details for a small sample (good UX; conversation_meta applies
    # pooled-mode pseudonyms when configured).
    sample = all_ids[:15]
    meta = dashboard.conversation_meta(sample, region=region) if sample else {}
    items = [
        {
            "conversation_id": cid,
            "region": meta.get(cid, {}).get("region"),
            "tenant_name": meta.get(cid, {}).get("tenant_name"),
            "title": meta.get(cid, {}).get("title"),
            "last_message_at": meta.get(cid, {}).get("last_message_at"),
        }
        for cid in sample
    ]
    return {
        "count": len(all_ids),
        "ids": all_ids[:1000],
        "by_region": by_region,
        "items": items,
        "region": region,
        "source": settings.source,
    }


@api.post("/analyze/sweep", status_code=202)
def analyze_sweep(region: str | None = Query(default=None)):
    """Step 2 of the manual flow: analyse every not-yet-analysed conversation for the selected
    region (or all). Deduped; runs in the background — poll GET /queue for progress. Returns
    'already_running' if a sweep is still in flight."""
    if settings.source != "chatdb":
        return problem_response(400, "Not available", "Manual analysis applies to the chat DB source only.")
    if (bad := _bad_region(region)) is not None:
        return bad
    started = trigger_sweep(region)
    return {"status": "started" if started else "already_running", "region": region, "source": settings.source}


@api.get("/stats")
def operational_stats(region: str | None = Query(default=None)):
    """Operational metrics: throughput, queue health, LLM vs rules, override + token totals."""
    from . import reporting

    if (bad := _bad_region(region)) is not None:
        return bad
    return reporting.operational_stats(store, analysis_queue, latest_run, region=region)


@api.get("/report")
def product_report(region: str | None = Query(default=None)):
    """Business report (J1-93353): category mix, high-frequency issues, new use-cases."""
    from . import reporting

    if (bad := _bad_region(region)) is not None:
        return bad
    return reporting.product_report(store, region=region)


@api.post("/runs")
def trigger_run():
    """Trigger a run (scheduler / reviewer). Re-analyses eligible, not-yet-analysed convs."""
    global latest_run
    latest_run = run_analysis(store, _load_source(), analyze_batch=make_batch_analyzer())
    return asdict(latest_run) | {"unanalysed": latest_run.unanalysed}


app.include_router(api)
