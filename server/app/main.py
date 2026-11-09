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

# Internal tool: allow the reviewer UI from loopback AND private-LAN addresses (RFC1918) on any
# port, so opening the UI via the host's LAN IP (e.g. http://10.19.8.252:3000) is not blocked by
# CORS. Public origins are still rejected; add explicit ones with CORS_ALLOW_ORIGINS.
_ALLOWED_ORIGIN_RE = (
    r"https?://("
    r"localhost|127\.0\.0\.1|\[::1\]"                 # loopback
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"                 # 10.0.0.0/8
    r"|192\.168\.\d{1,3}\.\d{1,3}"                    # 192.168.0.0/16
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"     # 172.16.0.0/12
    r")(:\d+)?"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()],
    allow_origin_regex=_ALLOWED_ORIGIN_RE,
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

def _eligible_by_region(
    region: str | None = None, env: str = "uit", feedback_only: bool = False
) -> dict[str, list[str]]:
    """{region_label: eligible ids} for an environment. One region if given, else all configured.
    When `feedback_only`, restrict to conversations that have user feedback (PROD 'feedback'
    scope). A region that errors (e.g. permission denied) is skipped so it can't block others."""
    from concurrent.futures import ThreadPoolExecutor

    from .chatdb import _eligible_in_region, configured_regions, resolve_region

    regions = [r for r in ([resolve_region(region, env)] if region else configured_regions(env)) if r is not None]
    out: dict[str, list[str]] = {}
    if not regions:
        return out

    lookback_days = settings.analysis_lookback_days(env)

    def _one(r):
        return r.label, _eligible_in_region(
            r, None, None, feedback_only=feedback_only, lookback_days=lookback_days
        )

    # Regions are independent remote chat DBs → query them concurrently (the eligibility scan can
    # be slow), skipping any that error so one bad region can't stop the rest.
    with ThreadPoolExecutor(max_workers=min(len(regions), 6)) as pool:
        futures = {pool.submit(_one, r): r for r in regions}
        for fut in futures:
            r = futures[fut]
            try:
                label, ids = fut.result()
                out[label] = ids
            except Exception as exc:  # noqa: BLE001 - one bad region must not stop the rest
                print(f"[warn] eligibility skipped region '{r.label}': {type(exc).__name__}", flush=True)
                out[r.label] = []
    return out


def _sweep(region: str | None = None, env: str = "uit", feedback_only: bool = False) -> None:
    """Enqueue every eligible, not-yet-analysed conversation for an environment (deduped by the
    queue). `feedback_only` restricts to conversations with user feedback. Pre-filters with a
    single analysed_ids() query so we don't fire one is_analysed() round-trip per id.
    Dead-lettered conversations are released first so THIS run retries them (reliability NFR)."""
    analysis_queue.retry_dead(env)  # failed analyses are retried in the next run (J1-93353)
    analysed = store.analysed_ids(env)
    eligible = _eligible_by_region(region, env, feedback_only)
    ids = [cid for ids in eligible.values() for cid in ids if cid not in analysed]
    analysis_queue.enqueue(ids, env)


_sweep_lock = threading.Lock()
_sweeps_running: set[str] = set()  # per-environment → UIT and PROD sweeps are independent


def trigger_sweep(region: str | None = None, env: str = "uit", feedback_only: bool = False) -> bool:
    """Manual trigger: run a check + analyse sweep in the background (deduped; only
    not-yet-analysed conversations are processed) for `region` (or all) in `env`. `feedback_only`
    restricts to feedback conversations. Dedup is per-environment: a running UIT sweep never blocks
    a PROD sweep (and vice-versa). Returns False if a sweep is already running for THIS env."""
    with _sweep_lock:
        if env in _sweeps_running:
            return False
        _sweeps_running.add(env)

    def _run() -> None:
        try:
            _sweep(region, env, feedback_only)
        except Exception as exc:  # noqa: BLE001 - chat DB may be unreachable; never crash
            print(f"[warn] manual sweep failed: {type(exc).__name__}", flush=True)
        finally:
            with _sweep_lock:
                _sweeps_running.discard(env)

    threading.Thread(target=_run, name="manual-sweep", daemon=True).start()
    return True


region_health: list[dict] = []  # per (env, region) connectivity, checked once at startup
if settings.source == "chatdb":
    # Test EVERY configured region of EVERY environment before serving: connect + verify tables.
    # We log and continue (a bad/permission-denied region must not crash the app or leak data).
    from .chatdb import check_regions

    for _env in settings.environments():
        region_health += check_regions(_env)
    for h in region_health:
        state = "OK " + str(h["counts"]) if h["ok"] else f"UNREACHABLE ({h['error']})"
        print(f"[startup] {h['env']}/{h['label']} {h['host']}/{h['db']}.{h['schema']}: {state}", flush=True)
    if not any(h["ok"] for h in region_health):
        print("[startup][warn] NO region is readable — dashboards will be empty until fixed.", flush=True)

    # MANUAL for both environments: analysis runs only when triggered from the UI
    # (POST /analyze/sweep, per-conversation analyse). No boot sweep, no scheduled cadence.
    analysis_queue.start()
    latest_run = run_analysis(store, [], analyze_batch=make_batch_analyzer())  # empty summary

    def _warm_dashboard() -> None:
        # Pre-open the dashboard connection pool + cache the schema-layout probe for every
        # env/region so the FIRST overview/feedback request isn't paying cold-connection cost.
        from . import dashboard

        for _e in settings.environments():
            try:
                dashboard.overview(store, env=_e)
            except Exception:  # noqa: BLE001 - best-effort warmup; never crash startup
                pass

    threading.Thread(target=_warm_dashboard, name="warmup", daemon=True).start()
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


def _env(env: str | None) -> str:
    """Normalise the environment label to a known one (uit/prod); unknown → uit."""
    from .config import valid_env

    return valid_env(env)


def _bad_region(region: str | None, env: str = "uit"):
    """Reject an unknown region label for the environment (strict — no cross-region leakage).
    An empty/None region means 'all regions' and is always valid."""
    if not region:
        return None
    from .chatdb import region_labels

    if region not in region_labels(env):
        return problem_response(400, "Invalid region", f"Unknown region: {region}")
    return None


def _metrics(record: AnalysisRecord) -> dict:
    return asdict(record.metrics)  # None values → JSON null (AC-7: unavailable, not zero)


def _last_message_at(conv: CommonConversation | None) -> str | None:
    if conv is None:
        return None
    value = max((message.created_at for message in conv.messages if message.created_at), default=None)
    return value.replace(" ", "T", 1) if value else None


def _has_thumbs(conv: CommonConversation | None) -> bool:
    """True if ANY feedback in the chat carries a thumb rating (multi-feedback aware, ADR-0022)."""
    if conv is None:
        return False
    return conv.feedback.rating is not None or any(f.rating is not None for f in conv.feedbacks)


def _list_item(
    record: AnalysisRecord,
    conv: CommonConversation | None,
    tenant_map: dict[str, str] | None = None,
    include_tenant: bool = False,
) -> dict:
    from .ea_customers import ea_info

    enrichment = record.enrichment
    item = {
        "conversation_id": record.conversation_id,
        "region": record.region or None,
        "title": getattr(conv, "title", None) if conv else None,
        "platform": enrichment.platform if enrichment else None,
        "interaction_mode": enrichment.interaction_mode if enrichment else None,
        "agent_used": enrichment.agent_used if enrichment else None,
        "category": record.category,
        "model_category": record.model_category,
        "recommended_next_step": record.recommended_next_step,
        "confidence": record.confidence,
        "status": record.status,
        "overridden": record.override is not None,
        "has_feedback": _has_thumbs(conv),
        "immediate_attention": record.signals.immediate_attention,
        "attention_reasons": record.signals.attention_reasons,
        "kb_issue": record.signals.kb_issue,
        "guardrail_bypass": record.signals.guardrail_bypass,
        "source_code": record.signals.source_code,
        "metrics": _metrics(record),
        "last_message_at": _last_message_at(conv),
        "analyzed_at": record.analyzed_at,
    }
    if include_tenant:
        tenant_id = str(record.tenant_id).strip() if record.tenant_id else None
        tenant_name = (tenant_map or {}).get(tenant_id or "") or (f"Tenant {tenant_id}" if tenant_id else None)
        item["tenant_id"] = tenant_id
        item["tenant_name"] = tenant_name
        item["ea"] = ea_info(tenant_name, tenant_id) if tenant_id or tenant_name else None
    return item


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api = APIRouter(prefix="/api/analysis", dependencies=[Depends(require_reviewer)])


@api.get("/environments")
def list_environments():
    """Environments available for the UI toggle (e.g. uit, prod), with per-region reachability."""
    envs = settings.environments() or ["uit"]
    return {
        "items": [
            {
                "env": e,
                "regions": [
                    {"label": h["label"], "reachable": h["ok"], "counts": h["counts"], "error": h["error"]}
                    for h in region_health if h.get("env") == e
                ],
            }
            for e in envs
        ],
        "default": "uit",
    }


@api.get("/regions")
def list_regions(env: str | None = Query(default=None)):
    """Regions available for the UI dropdown (for the selected env), with reachability + counts."""
    from .chatdb import configured_regions

    e = _env(env)
    health = {h["label"]: h for h in region_health if h.get("env") == e}
    return {
        "items": [
            {
                "label": r.label,
                "reachable": health.get(r.label, {}).get("ok"),
                "counts": health.get(r.label, {}).get("counts", {}),
                "error": health.get(r.label, {}).get("error"),
            }
            for r in configured_regions(e)
        ]
    }


def _item_activity_day(item: dict) -> date | None:
    value = item.get("last_message_at") or item.get("analyzed_at")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def _apply_date_window(items: list[dict], date_range: str | None, date_from: date | None, date_to: date | None) -> list[dict]:
    range_start = date_from
    range_end = date_to
    if date_range:
        range_end = datetime.now(timezone.utc).date()
        days = {"last_7_days": 6, "last_15_days": 14, "last_30_days": 29}.get(date_range, 29)
        range_start = range_end - timedelta(days=days)
    if not (range_start or range_end):
        return items
    return [
        item for item in items
        if (day := _item_activity_day(item)) is not None
        and (range_start is None or day >= range_start)
        and (range_end is None or day <= range_end)
    ]


def _immediate_analytics(items: list[dict]) -> dict:
    from collections import defaultdict

    reason_counts: dict[str, int] = {}
    last_15d_reason_counts: dict[str, int] = {}
    cutoff_15d = datetime.now(timezone.utc).date() - timedelta(days=14)
    region_counts: dict[str, int] = {}
    tenant_counts: dict[str, dict] = {}
    kb_by_day_map: dict[str, int] = defaultdict(int)
    kb_by_day_region_map: dict[str, dict[str, int]] = defaultdict(lambda: {"us": 0, "eu": 0, "uk": 0})
    kb_by_tenant_map: dict[str, dict] = {}
    serious_by_day_map: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "empty_final_response": 0,
            "guardrail_bypass": 0,
            "high_frustration": 0,
            "ticket_failure": 0,
            "other_serious": 0,
        }
    )
    reasons_by_day_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for item in items:
        reg = (item.get("region") or "unknown").lower()
        region_counts[reg] = region_counts.get(reg, 0) + 1
        tid = str(item.get("tenant_id") or "unknown")
        tname = str(item.get("tenant_name") or (f"Tenant {tid}" if tid != "unknown" else "Unknown tenant"))
        day_obj = _item_activity_day(item)
        day_str = day_obj.isoformat() if day_obj else "Unknown"

        reasons = list(item.get("attention_reasons") or [])
        for r in reasons:
            reason_counts[r] = reason_counts.get(r, 0) + 1
            if day_obj and day_obj >= cutoff_15d:
                last_15d_reason_counts[r] = last_15d_reason_counts.get(r, 0) + 1

        if item.get("immediate_attention") or item.get("kb_issue"):
            tentry = tenant_counts.setdefault(
                tid,
                {
                    "tenant_id": None if tid == "unknown" else tid,
                    "tenant_name": tname,
                    "region": item.get("region"),
                    "immediate_attention": 0,
                    "kb_issues": 0,
                    "empty_final_response": 0,
                    "guardrail_bypass": 0,
                    "total": 0,
                },
            )
            tentry["total"] += 1
            if item.get("immediate_attention"):
                tentry["immediate_attention"] += 1
            if item.get("kb_issue"):
                tentry["kb_issues"] += 1
            if "empty_final_response" in reasons:
                tentry["empty_final_response"] += 1
            if item.get("guardrail_bypass") or "guardrail_bypass" in reasons:
                tentry["guardrail_bypass"] += 1

        if item.get("kb_issue"):
            if day_obj:
                kb_by_day_map[day_str] += 1
                if reg in ("us", "eu", "uk"):
                    kb_by_day_region_map[day_str][reg] += 1
            kb_tenant = kb_by_tenant_map.setdefault(
                tid,
                {
                    "tenant_id": None if tid == "unknown" else tid,
                    "tenant_name": tname,
                    "region": item.get("region"),
                    "count": 0,
                },
            )
            kb_tenant["count"] += 1

        if day_obj and item.get("immediate_attention"):
            for r in reasons:
                reasons_by_day_map[day_str][r] += 1
            has_empty = "empty_final_response" in reasons
            has_bypass = bool(item.get("guardrail_bypass") or "guardrail_bypass" in reasons)
            has_frust = "high_frustration" in reasons
            has_ticket = "ticket_failure" in reasons
            other_serious = any(
                r not in {"empty_final_response", "guardrail_bypass", "high_frustration", "ticket_failure"}
                for r in reasons
            )
            if has_empty:
                serious_by_day_map[day_str]["empty_final_response"] += 1
            if has_bypass:
                serious_by_day_map[day_str]["guardrail_bypass"] += 1
            if has_frust:
                serious_by_day_map[day_str]["high_frustration"] += 1
            if has_ticket:
                serious_by_day_map[day_str]["ticket_failure"] += 1
            if other_serious:
                serious_by_day_map[day_str]["other_serious"] += 1

    sorted_reasons = sorted(reason_counts.items(), key=lambda pair: (-pair[1], pair[0]))
    sorted_15d_reasons = sorted(last_15d_reason_counts.items(), key=lambda pair: (-pair[1], pair[0]))
    top_reasons = [{"reason": r, "count": c} for r, c in sorted_15d_reasons[:3]]
    all_days = sorted(set(kb_by_day_map.keys()) | set(serious_by_day_map.keys()))
    return {
        "total_matching": len(items),
        "immediate_attention": sum(1 for item in items if item.get("immediate_attention")),
        "kb_issues": sum(1 for item in items if item.get("kb_issue")),
        "empty_final_response": sum(1 for item in items if "empty_final_response" in (item.get("attention_reasons") or [])),
        "guardrail_bypass": sum(1 for item in items if item.get("guardrail_bypass") or "guardrail_bypass" in (item.get("attention_reasons") or [])),
        "high_frustration": sum(1 for item in items if "high_frustration" in (item.get("attention_reasons") or [])),
        "ticket_failure": sum(1 for item in items if "ticket_failure" in (item.get("attention_reasons") or [])),
        "rate_limit": sum(1 for item in items if "rate_limit" in (item.get("attention_reasons") or [])),
        "affected_tenants": len({item.get("tenant_id") for item in items if item.get("tenant_id")}),
        "by_reason": dict(sorted_reasons),
        "top_reasons": top_reasons,
        "by_region": region_counts,
        "kb_by_day": [{"date": day, "count": kb_by_day_map.get(day, 0)} for day in all_days],
        "kb_by_day_region": [
            {
                "date": day,
                "us": kb_by_day_region_map[day]["us"],
                "eu": kb_by_day_region_map[day]["eu"],
                "uk": kb_by_day_region_map[day]["uk"],
                "total": sum(kb_by_day_region_map[day].values()),
            }
            for day in all_days
        ],
        "kb_by_tenant": sorted(kb_by_tenant_map.values(), key=lambda row: row["count"], reverse=True)[:12],
        "serious_by_day": [
            {
                "date": day,
                "empty_final_response": serious_by_day_map[day]["empty_final_response"],
                "guardrail_bypass": serious_by_day_map[day]["guardrail_bypass"],
                "high_frustration": serious_by_day_map[day]["high_frustration"],
                "ticket_failure": serious_by_day_map[day]["ticket_failure"],
                "other_serious": serious_by_day_map[day]["other_serious"],
                "by_reason": dict(reasons_by_day_map[day]),
                "total": sum(serious_by_day_map[day].values()),
            }
            for day in all_days
        ],
        "top_tenants": sorted(tenant_counts.values(), key=lambda row: (row["total"], row["immediate_attention"]), reverse=True)[:12],
    }


@api.get("/conversations")
def list_conversations(
    category: str | None = Query(default=None),
    region: str | None = Query(default=None),
    env: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    tenant: str | None = Query(default=None, max_length=200),
    confidence: str | None = Query(default=None),
    review_state: str | None = Query(default=None),
    attention_reason: str | None = Query(default=None, max_length=50),
    has_feedback: str | None = Query(default=None, pattern="^(yes|no)$"),
    date_range: str | None = Query(default=None, pattern="^(last_7_days|last_15_days|last_30_days)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    include_analytics: bool = Query(default=False),
    sort: str = Query(default="newest"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    env = _env(env)
    if category is not None and category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {category}")
    if (bad := _bad_region(region, env)) is not None:
        return bad
    if confidence is not None and confidence not in {"high", "medium", "low"}:
        return problem_response(400, "Invalid confidence", f"Unknown confidence: {confidence}")
    if review_state is not None and review_state not in {"attention", "immediate_attention", "kb_issue", "immediate_or_kb", "feedback", "overridden", "missing_telemetry"}:
        return problem_response(400, "Invalid review state", f"Unknown review state: {review_state}")
    if date_from and date_to and date_from > date_to:
        return problem_response(400, "Invalid date range", "date_from must be on or before date_to")
    if sort not in {"newest", "oldest", "attention", "confidence", "slowest", "tokens"}:
        return problem_response(400, "Invalid sort", f"Unknown sort: {sort}")

    include_tenant = bool(include_analytics or tenant)
    tenant_map: dict[str, str] = {}
    if include_tenant:
        try:
            from . import dashboard

            tenant_map = dashboard.tenant_names(region=region, env=env)
        except Exception:  # noqa: BLE001
            tenant_map = {}

    records = store.list(category=category, region=region, env=env)  # type: ignore[arg-type]
    conversations = store.get_conversations([record.conversation_id for record in records], env)
    all_items = [
        _list_item(record, conversations.get(record.conversation_id), tenant_map, include_tenant=include_tenant)
        for record in records
    ]
    items = list(all_items)
    text_query = (query or "").strip().lower()
    tenant_query = (tenant or "").strip().lower()
    if text_query:
        items = [
            item for item in items
            if any(
                text_query in str(item.get(field) or "").lower()
                for field in ("conversation_id", "title", "tenant_id", "tenant_name", "recommended_next_step")
            )
        ]
    if tenant_query:
        items = [
            item for item in items
            if tenant_query in str(item.get("tenant_id") or "").lower()
            or tenant_query in str(item.get("tenant_name") or "").lower()
        ]
    if confidence:
        items = [item for item in items if item["confidence"] == confidence]
    if has_feedback == "yes":
        items = [item for item in items if item["has_feedback"]]
    elif has_feedback == "no":
        items = [item for item in items if not item["has_feedback"]]
    items = _apply_date_window(items, date_range, date_from, date_to)

    analytics_pool = [
        item for item in items
        if item["immediate_attention"] or item["kb_issue"]
    ]
    if review_state == "attention":
        items = [item for item in items if item["category"] in {"failed_to_resolve", "negative_feedback", "out_of_scope"} or item["immediate_attention"]]
    elif review_state == "immediate_attention":
        items = [item for item in items if item["immediate_attention"]]
    elif review_state == "kb_issue":
        items = [item for item in items if item["kb_issue"]]
    elif review_state == "immediate_or_kb":
        items = [item for item in items if item["immediate_attention"] or item["kb_issue"]]
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
    if attention_reason:
        if attention_reason == "kb_issue":
            items = [item for item in items if item["kb_issue"]]
        else:
            items = [item for item in items if attention_reason in item["attention_reasons"]]

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
        items.sort(key=lambda item: (not item["immediate_attention"], priority.get(item["category"], 9)))

    total = len(items)
    page_items = items[offset : offset + limit]
    missing_meta_ids = (
        [item["conversation_id"] for item in page_items if not item.get("tenant_id") or not item.get("title")]
        if include_tenant
        else []
    )
    if missing_meta_ids:
        try:
            from . import dashboard

            meta = dashboard.conversation_meta(missing_meta_ids, region=region, env=env)
            for item in page_items:
                m = meta.get(item["conversation_id"])
                if m:
                    item["tenant_id"] = item.get("tenant_id") or m.get("tenant_id")
                    item["tenant_name"] = item.get("tenant_name") or m.get("tenant_name")
                    item["ea"] = item.get("ea") or m.get("ea")
                    item["title"] = item.get("title") or m.get("title")
        except Exception:  # noqa: BLE001
            pass

    response = {
        "items": page_items,
        "counts": store.count_by_category(region=region, env=env),
        "total": total,
        # Region-scoped when a region is selected (matches the region-filtered items/counts);
        # env-wide when listing all regions. Unknown-region failures only show in the latter.
        "unanalysed": store.unanalysed_count(env, region=region),
        "region": region,
        "environment": env,
        "limit": limit,
        "offset": offset,
    }
    if include_analytics:
        response["analytics"] = _immediate_analytics(analytics_pool if review_state in {"immediate_attention", "kb_issue", "immediate_or_kb"} else items)
    return response



def _conversation_detail(conversation_id: str, env: str = "uit") -> dict | None:
    record = store.get_analysis(conversation_id, env)
    conv = store.get_conversation(conversation_id, env)
    if record is None or conv is None:
        return None
    source = None
    try:
        from . import dashboard

        source = dashboard.conversation_meta([conversation_id], env=env).get(conversation_id)
    except Exception:  # noqa: BLE001 - chat DB optional; detail still works de-identified
        source = None
    enrichment = record.enrichment
    if record.region and (
        enrichment is None or (enrichment.langsmith_found and not enrichment.trace_id)
    ):
        from .enrichment import fetch_enrichment

        fetched = fetch_enrichment(
            conversation_id,
            record.region,
            env,
            with_prompt=_has_thumbs(conv),
        )
        if fetched is not None and (enrichment is None or fetched.trace_id):
            record.enrichment = fetched
            store.upsert(record, conv)
            enrichment = fetched
    return {
        "conversation_id": conversation_id,
        "source": source,  # tenant/user/title/timestamps (authorised admin view)
        "analysis": {
            "region": record.region or None,
            "category": record.category,
            "model_category": record.model_category,
            "recommended_next_step": record.recommended_next_step,
            "confidence": record.confidence,
            "rationale": record.rationale,
            "signals": asdict(record.signals),
            "status": record.status,
            "override": asdict(record.override) if record.override else None,
            # Append-only audit trail: EVERY override ever applied, oldest first (J1-93353).
            "override_history": [asdict(o) for o in store.override_events(conversation_id, env)],
            "run_id": record.run_id,
            "analyzer_version": record.analyzer_version,
            "analyzed_at": record.analyzed_at,
        },
        "deep": asdict(record.deep) if record.deep else None,
        "enrichment": asdict(enrichment) if enrichment else None,
        "metrics": _metrics(record),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sequence_num": m.sequence_num,
                "model": m.model,
                "created_at": m.created_at,
                "status": m.status,
                "error_message": m.error_message,
                # Per-message generation telemetry (FR-4): null = not captured (AC-7), never 0.
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "prompt_tokens": m.prompt_tokens,
                "ttft_ms": m.ttft_ms,
            }
            for m in conv.messages
        ],
        "feedback": {"rating": conv.feedback.rating, "comment": conv.feedback.comment},
        # ALL feedback in the chat, each tied to its turn/message (ADR-0022).
        "feedbacks": [
            {"rating": f.rating, "comment": f.comment, "message_id": f.message_id}
            for f in conv.feedbacks
        ],
    }


@api.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, env: str | None = Query(default=None)):
    payload = _conversation_detail(conversation_id, _env(env))
    if payload is None:
        return problem_response(404, "Not found", f"No analysis for conversation {conversation_id}")
    return payload


_NEGATIVE_CATEGORIES = {"negative_feedback", "failed_to_resolve"}


@api.get("/feedback")
def feedback_conversations(
    scope: str = Query(default="thumbs", pattern="^(thumbs|outcomes|all)$"),
    region: str | None = Query(default=None),
    env: str | None = Query(default=None),
    rating: str | None = Query(default=None, pattern="^(positive|negative)$"),
    category: str | None = Query(default=None),
    root_cause: str | None = Query(default=None, max_length=40),
    query: str | None = Query(default=None, max_length=200),
    tenant: str | None = Query(default=None, max_length=200),
    date_range: str | None = Query(default=None, pattern="^(last_7_days|last_30_days)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|oldest|negative_first)$"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Feedback / negative-signal records, one rich row per rated message for a reviewer table.

    scope=thumbs (default): only EXPLICIT thumbs feedback (up/down).
    scope=outcomes: conversations the model judged negative (failed_to_resolve /
        negative_feedback) even without a thumb — the large 'went badly' set.
    scope=all: union of both.
    """
    env = _env(env)
    if (bad := _bad_region(region, env)) is not None:
        return bad
    if category is not None and category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {category}")
    if date_from and date_to and date_from > date_to:
        return problem_response(400, "Invalid date range", "date_from must be on or before date_to")
    items = []
    records = store.list(region=region, env=env)
    conversations = store.get_conversations([record.conversation_id for record in records], env)
    for record in records:
        conv = conversations.get(record.conversation_id)
        feedbacks = list(conv.feedbacks) if conv else []
        if conv and not feedbacks and (conv.feedback.rating is not None or conv.feedback.comment):
            feedbacks = [conv.feedback]
        rated_feedbacks = [feedback for feedback in feedbacks if feedback.rating is not None]
        has_thumbs = bool(rated_feedbacks)
        neg_outcome = record.category in _NEGATIVE_CATEGORIES
        if scope == "thumbs" and not has_thumbs:
            continue
        if scope == "outcomes" and not neg_outcome:
            continue
        if scope == "all" and not (has_thumbs or neg_outcome):
            continue
        m = record.metrics
        deep = asdict(record.deep) if record.deep else None
        ordered_messages = list(conv.messages) if conv else []
        messages = {message.id: message for message in ordered_messages}
        msg_index = {message.id: idx for idx, message in enumerate(ordered_messages)}
        events = rated_feedbacks or [None]
        for index, feedback in enumerate(events):
            message_id = feedback.message_id if feedback else None
            message = messages.get(message_id) if message_id else None
            turn_number = None
            user_query = None
            if message_id and message_id in msg_index:
                pos_idx = msg_index[message_id]
                turn_number = sum(1 for msg in ordered_messages[: pos_idx + 1] if msg.role == "assistant")
                for prev in reversed(ordered_messages[:pos_idx]):
                    if prev.role == "user" and (prev.content or "").strip():
                        user_query = prev.content.strip()[:160]
                        break
            enrichment = record.enrichment
            items.append(
                {
                    "feedback_id": f"{record.conversation_id}:{message_id or index}",
                    "feedback_message_id": message_id,
                    "turn_number": turn_number,
                    "user_query": user_query,
                    "feedback_at": message.created_at if message else None,
                    "conversation_id": record.conversation_id,
                    "category": record.category,
                    "model_category": record.model_category,
                    "confidence": record.confidence,
                    "rating": feedback.rating if feedback else None,
                    "comment": feedback.comment if feedback else None,
                    "feedbacks": [
                        {"rating": f.rating, "comment": f.comment, "message_id": f.message_id}
                        for f in feedbacks
                    ],
                    "has_thumbs": has_thumbs,
                    "immediate_attention": record.signals.immediate_attention,
                    "attention_reasons": record.signals.attention_reasons,
                    "kb_issue": record.signals.kb_issue,
                    "guardrail_bypass": record.signals.guardrail_bypass,
                    "source_code": record.signals.source_code,
                    "platform": enrichment.platform if enrichment else None,
                    "interaction_mode": enrichment.interaction_mode if enrichment else None,
                    "agent_used": enrichment.agent_used if enrichment else None,
                    "recommended_next_step": record.recommended_next_step,
                    "rationale": record.rationale,
                    "why_it_happened": (deep or {}).get("why_it_happened", ""),
                    # Same derivation as the /groups endpoint (LLM label OR deterministic fallback) so
                    # the Insights drill-in (?root_cause=…) matches the group it came from.
                    "root_cause": _record_root_cause(record),
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
    if root_cause:  # drill-in from the Insights groups view
        items = [item for item in items if item.get("root_cause") == root_cause]

    # enrich with source metadata (tenant/user/title/timestamps) so the UI can show a table
    def _enrich(rows):
        try:
            from . import dashboard

            meta = dashboard.conversation_meta([item["conversation_id"] for item in rows], region=region, env=env)
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
                    "conversation_id", "feedback_message_id", "comment", "title", "tenant_name", "user_name",
                    "platform", "interaction_mode", "agent_used", "recommended_next_step", "why_it_happened",
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
            value = item.get("last_message_at") or item.get("feedback_at") or item.get("analyzed_at")
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
        items.sort(key=lambda item: item["feedback_at"] or item["last_message_at"] or item["analyzed_at"] or "", reverse=True)
    elif sort == "oldest":
        items.sort(key=lambda item: item["feedback_at"] or item["last_message_at"] or item["analyzed_at"] or "")
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


_ROOT_CAUSE_LABELS = {
    "guardrail_bypass": "Guardrail bypass / internal detail exposure",
    "knowledge_gap": "Knowledge gap (right document not retrieved)",
    "wrong_document_retrieved": "Wrong documents retrieved",
    "wrong_routing": "Wrong routing / out of scope",
    "ambiguous_question": "Ambiguous question",
    "tool_error": "Tool / system error",
    "missing_tenant_rule": "Missing tenant rule",
    "other": "Other",
}


def _record_root_cause(record: AnalysisRecord) -> str:
    """Root-cause label for a record: the LLM label if present, else derived from safe signals."""
    if record.signals.guardrail_bypass:
        return "guardrail_bypass"
    if record.signals.kb_issue:
        return "knowledge_gap"
    if record.deep and record.deep.root_cause:
        return record.deep.root_cause
    e = record.enrichment
    if e is not None:
        if e.retrieval_hit is False:
            return "knowledge_gap"
        if e.had_error is True:
            return "tool_error"
        if (e.guardrail or "").lower() in ("reject", "refusal", "handoff"):
            return "wrong_routing"
    return "other"


@api.get("/groups")
def root_cause_groups(
    scope: str = Query(default="issues", pattern="^(issues|all)$"),
    region: str | None = Query(default=None),
    env: str | None = Query(default=None),
):
    """Group conversations by root cause and rank by impact (ADR-0022).

    scope=issues (default): conversations that went badly — any thumbs feedback OR a negative
        outcome (failed_to_resolve / negative_feedback). scope=all: every analysed conversation.
    Impact counts are aggregate only: conversations, distinct tenants (tenant_id), and distinct
    users (one-way user_hash pseudonym). No tenant/user identity is returned.
    """
    env = _env(env)
    if (bad := _bad_region(region, env)) is not None:
        return bad
    records = store.list(region=region, env=env)
    conversations = store.get_conversations([r.conversation_id for r in records], env)
    groups: dict[str, dict] = {}
    for record in records:
        conv = conversations.get(record.conversation_id)
        include = scope == "all" or _has_thumbs(conv) or record.category in _NEGATIVE_CATEGORIES or record.signals.immediate_attention or record.signals.kb_issue
        if not include:
            continue
        rc = _record_root_cause(record)
        g = groups.setdefault(rc, {"ids": [], "tenants": set(), "users": set(), "step": ""})
        g["ids"].append(record.conversation_id)
        if record.tenant_id:
            g["tenants"].add(record.tenant_id)
        if record.user_hash:
            g["users"].add(record.user_hash)
        step = record.recommended_next_step
        if not g["step"] and step and step != "No action needed.":
            g["step"] = step
    items = [
        {
            "root_cause": rc,
            "label": _ROOT_CAUSE_LABELS.get(rc, rc),
            "knowledge_gap": rc == "knowledge_gap",
            "conversations": len(g["ids"]),
            "tenants": len(g["tenants"]),
            "users": len(g["users"]),
            "sample_conversation_ids": g["ids"][:5],
            "example_next_step": g["step"],
        }
        for rc, g in groups.items()
    ]
    items.sort(key=lambda x: (x["conversations"], x["users"], x["tenants"]), reverse=True)
    return {"items": items, "total": len(items), "scope": scope}


@api.get("/feedback/export")
def feedback_export(
    format: str = Query(default="csv", pattern="^(csv|json|pdf)$"),
    scope: str = Query(default="all", pattern="^(thumbs|outcomes|all)$"),
    region: str | None = Query(default=None),
    env: str | None = Query(default=None),
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
    env = _env(env)
    if (bad := _bad_region(region, env)) is not None:
        return bad
    if category is not None and category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {category}")
    if date_from and date_to and date_from > date_to:
        return problem_response(400, "Invalid date range", "date_from must be on or before date_to")
    from . import export

    rows = export.collect_rows(
        store, scope=scope, region=region, rating=rating, category=category,
        query=query, tenant=tenant, date_range=date_range,
        date_from=date_from, date_to=date_to, sort=sort, env=env,
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
def analyze_conversation(conversation_id: str, env: str | None = Query(default=None)):
    """On-demand (re)analyse ONE conversation now (any environment — this is how PROD
    conversations get analysed). Capped at MAX_ANALYSES_PER_DAY per convo per env."""
    import uuid
    from datetime import datetime, timezone

    from .chatdb import load_one_from_chatdb
    from .deidentify import deidentify

    env = _env(env)
    if store.analyses_today(conversation_id, env=env) >= settings.max_analyses_per_day:
        return problem_response(
            429, "Daily analyse limit reached",
            f"This conversation was already analysed {settings.max_analyses_per_day} times today.",
        )
    try:
        conv = load_one_from_chatdb(conversation_id, env=env)
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)
    if conv is None:
        return problem_response(404, "Not found", f"No source conversation {conversation_id}")
    if not conv.messages:  # empty conversation → nothing to analyse (avoid a hallucinated label)
        return problem_response(422, "No transcript", "This conversation has no messages to analyse.")

    now = datetime.now(timezone.utc)
    records = make_batch_analyzer()([conv], f"ondemand_{uuid.uuid4().hex[:8]}", now.isoformat())
    if not records:
        store.mark_failed(conversation_id, env, conv.region)
        return problem_response(503, "Analysis failed", "model unavailable; please retry")
    store.record_analysis(conversation_id, now.isoformat(), env)
    store.upsert(records[0], deidentify(conv))
    return _conversation_detail(conversation_id, env)


class OverrideBody(BaseModel):
    category: str
    actor: str


@api.post("/conversations/{conversation_id}/override")
def override_category(conversation_id: str, body: OverrideBody, env: str | None = Query(default=None)):
    if body.category not in CATEGORIES:
        return problem_response(400, "Invalid category", f"Unknown category: {body.category}")
    record = store.set_override(conversation_id, body.category, body.actor, _env(env))  # type: ignore[arg-type]
    if record is None:
        return problem_response(404, "Not found", f"No analysis for conversation {conversation_id}")
    return {
        "conversation_id": record.conversation_id,
        "category": record.category,
        "model_category": record.model_category,
        "recommended_next_step": record.recommended_next_step,
        "override": asdict(record.override) if record.override else None,
        "override_history": [asdict(o) for o in store.override_events(conversation_id, _env(env))],
    }


@api.get("/runs/latest")
def latest_run_summary():
    return asdict(latest_run) | {"unanalysed": latest_run.unanalysed}


# ── Admin dashboard: tenant → user → conversation drill-down (authorised view) ──
@api.get("/dashboard/overview")
def dashboard_overview(region: str | None = Query(default=None), env: str | None = Query(default=None)):
    from . import dashboard

    env = _env(env)
    if (bad := _bad_region(region, env)) is not None:
        return bad
    try:
        return dashboard.overview(store, region=region, env=env)
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
def dashboard_tenants(region: str | None = Query(default=None), env: str | None = Query(default=None)):
    from . import dashboard

    env = _env(env)
    if (blocked := _pooled_block()) is not None:
        return blocked
    if (bad := _bad_region(region, env)) is not None:
        return bad
    try:
        return {"items": dashboard.tenants(region=region, env=env), "region": region, "environment": env}
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


@api.get("/dashboard/tenants/{tenant_id}/users")
def dashboard_users(tenant_id: str, region: str | None = Query(default=None), env: str | None = Query(default=None)):
    from . import dashboard

    env = _env(env)
    if (blocked := _pooled_block()) is not None:
        return blocked
    if (bad := _bad_region(region, env)) is not None:
        return bad
    try:
        return {"items": dashboard.users(tenant_id, region=region, env=env), "region": region, "environment": env}
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)


@api.get("/dashboard/tenants/{tenant_id}/users/{user_id}/conversations")
def dashboard_user_conversations(
    tenant_id: str,
    user_id: str,
    region: str | None = Query(default=None),
    env: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from . import dashboard

    env = _env(env)
    if (blocked := _pooled_block()) is not None:
        return blocked
    if (bad := _bad_region(region, env)) is not None:
        return bad
    try:
        items, total = dashboard.user_conversations(store, tenant_id, user_id, limit, offset, region=region, env=env)
    except Exception as exc:  # noqa: BLE001
        return problem_response(503, "Chat DB unavailable", type(exc).__name__)

    # Lazy analyse: UIT only. PROD is opt-in (per-conversation button / feedback-only sweep), so
    # browsing PROD never triggers analysis of its huge conversation volume.
    if settings.lazy_analyze and env == "uit":
        pending = [it["conversation_id"] for it in items if it["status"] == "pending"]
        accepted = set(analysis_queue.enqueue(pending, env)) if pending else set()
        for it in items:
            if it["conversation_id"] in accepted:
                it["status"] = "analysing"
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@api.get("/queue")
def queue_stats(
    env: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Queue health for the selected environment (UIT and PROD are separate views): depth,
    in-flight, dead-letter, capacity, workers."""
    return analysis_queue.stats(limit=limit, offset=offset, env=_env(env))


def _pending_feedback_summary(by_ids: dict[str, list[str]], env: str) -> dict:
    empty = {
        "feedback_messages": 0,
        "positive_feedback_messages": 0,
        "negative_feedback_messages": 0,
        "positive_feedback_conversations": 0,
        "negative_feedback_conversations": 0,
        "negative_by_region": {},
        "negative_by_mode": {},
        "negative_by_platform": {},
        "deep_research_negative": 0,
        "average_frustration": None,
        "frustration_scored_messages": 0,
        "negative_items": [],
        "details_complete": True,
    }
    ids = [cid for region_ids in by_ids.values() for cid in region_ids]
    if not ids:
        return empty

    from concurrent.futures import ThreadPoolExecutor

    from . import dashboard
    from .chatdb import load_from_chatdb
    from .enrichment import fetch_enrichment

    conversations = load_from_chatdb(ids=ids, env=env)
    events = []
    positive_messages = 0
    positive_conversations = 0
    negative_conversations = 0
    per_conversation_counts: dict[str, dict[str, int]] = {}
    by_conversation = {conversation.id: conversation for conversation in conversations}
    for conversation in conversations:
        ordered_messages = list(conversation.messages)
        messages = {message.id: message for message in ordered_messages}
        msg_index = {message.id: idx for idx, message in enumerate(ordered_messages)}
        feedbacks = conversation.feedbacks or [conversation.feedback]
        neg_n = sum(1 for feedback in feedbacks if feedback.rating is False)
        pos_n = sum(1 for feedback in feedbacks if feedback.rating is True)
        per_conversation_counts[conversation.id] = {"negative": neg_n, "positive": pos_n}
        has_negative = neg_n > 0
        has_positive = pos_n > 0
        if has_negative:
            negative_conversations += 1
        elif has_positive:
            positive_conversations += 1
        for index, feedback in enumerate(feedbacks):
            if feedback.rating is True:
                positive_messages += 1
                continue
            if feedback.rating is not False:
                continue
            message = messages.get(feedback.message_id) if feedback.message_id else None
            user_query = None
            turn_number = None
            if feedback.message_id and feedback.message_id in msg_index:
                pos_idx = msg_index[feedback.message_id]
                turn_number = sum(1 for m in ordered_messages[: pos_idx + 1] if m.role == "assistant")
                for prev in reversed(ordered_messages[:pos_idx]):
                    if prev.role == "user" and (prev.content or "").strip():
                        user_query = prev.content.strip()[:160]
                        break
            events.append(
                {
                    "feedback_id": f"{conversation.id}:{feedback.message_id or index}",
                    "conversation_id": conversation.id,
                    "feedback_message_id": feedback.message_id,
                    "turn_number": turn_number,
                    "user_query": user_query,
                    "comment": feedback.comment,
                    "feedback_at": message.created_at if message else None,
                    "region": conversation.region,
                    "title": conversation.title,
                }
            )
    events.sort(key=lambda item: item["feedback_at"] or "", reverse=True)
    if not events:
        return empty | {
            "feedback_messages": positive_messages,
            "positive_feedback_messages": positive_messages,
            "positive_feedback_conversations": positive_conversations,
            "per_conversation_counts": per_conversation_counts,
        }

    enrichment_ids = list(dict.fromkeys(event["conversation_id"] for event in events))[:20]
    with ThreadPoolExecutor(max_workers=min(2, len(enrichment_ids))) as pool:
        enrichment = {
            cid: result
            for cid, result in zip(
                enrichment_ids,
                pool.map(
                    lambda cid: fetch_enrichment(
                        cid,
                        by_conversation[cid].region,
                        env,
                        with_prompt=True,
                    ),
                    enrichment_ids,
                ),
            )
        }
    display_ids = list(dict.fromkeys(event["conversation_id"] for event in events[:50]))
    try:
        meta = dashboard.conversation_meta(display_ids, env=env)
    except Exception:
        meta = {}

    by_region: dict[str, int] = {}
    by_mode: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    frustration_scores = []
    items = []
    for event in events:
        details = enrichment.get(event["conversation_id"])
        mode = details.interaction_mode if details and details.interaction_mode else "Unknown"
        platform = details.platform if details and details.platform else "Unknown"
        frustration = details.frustration_score if details else None
        region = event["region"] or "unknown"
        by_region[region] = by_region.get(region, 0) + 1
        by_mode[mode] = by_mode.get(mode, 0) + 1
        by_platform[platform] = by_platform.get(platform, 0) + 1
        if frustration is not None:
            frustration_scores.append(frustration)
        if len(items) < 50:
            source = meta.get(event["conversation_id"], {})
            items.append(
                event
                | {
                    "tenant_name": source.get("tenant_name"),
                    "title": source.get("title") or event["title"],
                    "platform": platform,
                    "interaction_mode": mode,
                    "agent_used": details.agent_used if details else None,
                    "frustration_score": frustration,
                }
            )

    return {
        "feedback_messages": positive_messages + len(events),
        "positive_feedback_messages": positive_messages,
        "negative_feedback_messages": len(events),
        "positive_feedback_conversations": positive_conversations,
        "negative_feedback_conversations": negative_conversations,
        "negative_by_region": by_region,
        "negative_by_mode": by_mode,
        "negative_by_platform": by_platform,
        "deep_research_negative": by_mode.get("Deep Research", 0),
        "average_frustration": round(sum(frustration_scores) / len(frustration_scores), 2) if frustration_scores else None,
        "frustration_scored_messages": len(frustration_scores),
        "negative_items": items,
        "per_conversation_counts": per_conversation_counts,
        "details_complete": len(enrichment_ids) == len({event["conversation_id"] for event in events}),
    }


@api.get("/analyze/pending")
def analyze_pending(
    region: str | None = Query(default=None),
    env: str | None = Query(default=None),
    scope: str = Query(default="all", pattern="^(all|feedback)$"),
):
    """Step 1 of the manual flow: FETCH (don't analyse) the eligible, not-yet-analysed
    conversations for the selected region (or all regions), returning the total, a per-region
    breakdown, and brief details for a sample. `scope=feedback` restricts to conversations with
    user feedback (PROD shows feedback + all as two separate lists)."""
    env = _env(env)
    lookback_days = settings.analysis_lookback_days(env)
    if settings.source != "chatdb":
        return {"count": 0, "ids": [], "by_region": {}, "items": [], "region": region, "environment": env, "scope": scope, "source": settings.source, "analysis_window_days": lookback_days}
    if (bad := _bad_region(region, env)) is not None:
        return bad
    from . import dashboard

    analysed = store.analysed_ids(env)
    # Exclude conversations that are already being processed (queued / in-flight / retrying) so a
    # second Analyze click mid-run does NOT re-list the same work as if it were new. Dead-lettered
    # ids stay IN the count (the next sweep's retry_dead re-runs them) but are also surfaced as
    # `failed`. This is what makes the "waiting" number honest between clicks.
    in_progress = analysis_queue.in_progress_ids(env)
    dead = analysis_queue.dead_ids(env)
    skip = analysed | in_progress
    eligible = _eligible_by_region(region, env, feedback_only=(scope == "feedback"))
    by_ids = {lbl: [i for i in ids if i not in skip] for lbl, ids in eligible.items()}
    by_region = {lbl: len(ids) for lbl, ids in by_ids.items()}
    all_ids = [i for ids in by_ids.values() for i in ids]
    # Only enrich a bounded sample for the preview list — the 'all' scope in PROD can be huge and
    # conversation_meta joins the chat DB, so meta for every id would be slow. The count is exact.
    candidates = [cid for ids in by_ids.values() for cid in ids[:50]]
    meta = dashboard.conversation_meta(candidates, region=region, env=env) if candidates else {}
    sample = sorted(
        candidates,
        key=lambda cid: meta.get(cid, {}).get("last_message_at") or "",
        reverse=True,
    )[:50]
    feedback_summary = _pending_feedback_summary(by_ids, env) if scope == "feedback" else {}
    per_conv = feedback_summary.pop("per_conversation_counts", {}) if isinstance(feedback_summary, dict) else {}
    items = [
        {
            "conversation_id": cid,
            "region": meta.get(cid, {}).get("region"),
            "tenant_name": meta.get(cid, {}).get("tenant_name"),
            "title": meta.get(cid, {}).get("title"),
            "last_message_at": meta.get(cid, {}).get("last_message_at"),
            "negative_count": per_conv.get(cid, {}).get("negative"),
            "positive_count": per_conv.get(cid, {}).get("positive"),
        }
        for cid in sample
    ]
    return {
        "count": len(all_ids),
        "ids": all_ids,
        "by_region": by_region,
        "items": items,
        "in_progress": len(in_progress),  # already queued/analysing — will finish without a new sweep
        "failed": len(dead),              # dead-lettered; the next Analyze retries them
        **feedback_summary,
        "region": region,
        "environment": env,
        "scope": scope,
        "analysis_window_days": lookback_days,
        "source": settings.source,
    }


@api.post("/analyze/sweep", status_code=202)
def analyze_sweep(
    region: str | None = Query(default=None),
    env: str | None = Query(default=None),
    scope: str = Query(default="all", pattern="^(all|feedback)$"),
):
    """Step 2 of the manual flow: analyse not-yet-analysed conversations for the selected region
    (or all) in the environment. `scope=feedback` restricts to feedback conversations; `scope=all`
    analyses every conversation. Deduped; runs in the background — poll GET /queue for progress."""
    env = _env(env)
    if settings.source != "chatdb":
        return problem_response(400, "Not available", "Manual analysis applies to the chat DB source only.")
    if (bad := _bad_region(region, env)) is not None:
        return bad
    started = trigger_sweep(region, env, feedback_only=(scope == "feedback"))
    return {"status": "started" if started else "already_running", "region": region, "environment": env, "scope": scope, "source": settings.source}


@api.get("/stats")
def operational_stats(region: str | None = Query(default=None), env: str | None = Query(default=None)):
    """Operational metrics: throughput, queue health, LLM vs rules, override + token totals."""
    from . import reporting

    env = _env(env)
    if (bad := _bad_region(region, env)) is not None:
        return bad
    return reporting.operational_stats(store, analysis_queue, latest_run, region=region, env=env)


@api.get("/report")
def product_report(region: str | None = Query(default=None), env: str | None = Query(default=None)):
    """Business report (J1-93353): category mix, high-frequency issues, new use-cases."""
    from . import reporting

    env = _env(env)
    if (bad := _bad_region(region, env)) is not None:
        return bad
    return reporting.product_report(store, region=region, env=env)


@api.post("/runs")
def trigger_run():
    """Trigger a run (scheduler / reviewer). Re-analyses eligible, not-yet-analysed convs."""
    global latest_run
    latest_run = run_analysis(store, _load_source(), analyze_batch=make_batch_analyzer())
    return asdict(latest_run) | {"unanalysed": latest_run.unanalysed}


app.include_router(api)
