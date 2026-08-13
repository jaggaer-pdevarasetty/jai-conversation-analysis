"""Reporting + operational metrics over the analysed conversations (J1-93353 reporting layer).

Two views:
- `operational_stats`: how the system is doing (throughput, queue health, LLM vs rules,
  token cost) — for observability dashboards / alerts.
- `product_report`: what the analysis is telling the business — category mix, the
  highest-frequency issues, and popular new use-cases (out-of-scope requests).

Pure functions over the store, so they are trivially testable.
"""

from __future__ import annotations

from collections import Counter

from .store import CommonStore


def operational_stats(store: CommonStore, queue=None, latest_run=None) -> dict:
    records = store.list()
    tokens_in = sum((r.metrics.input_tokens or 0) for r in records)
    tokens_out = sum((r.metrics.output_tokens or 0) for r in records)
    stats: dict = {
        "analysed": len(records),
        "unanalysed": store.unanalysed_count(),
        "counts": store.count_by_category(),
        "analyzers": dict(Counter(r.analyzer_version for r in records)),  # vertex vs rules
        "by_region": dict(Counter((r.region or "unknown") for r in records)),
        "overrides": sum(1 for r in records if r.override is not None),
        "tokens": {"input": tokens_in, "output": tokens_out, "total": tokens_in + tokens_out},
    }
    if latest_run is not None:
        stats["latest_run"] = {
            "run_id": latest_run.run_id,
            "analysed": latest_run.analysed,
            "failed": latest_run.failed,
            "skipped": latest_run.skipped,
        }
    if queue is not None:
        stats["queue"] = queue.stats()
    return stats


def product_report(store: CommonStore, top: int = 10) -> dict:
    records = store.list()
    total = len(records)
    denom = total or 1
    counts = store.count_by_category()
    distribution = {c: {"count": n, "pct": round(100 * n / denom, 1)} for c, n in counts.items()}

    # High-frequency issues: the most common recommended next steps on unresolved chats.
    failed_steps = Counter(
        r.recommended_next_step for r in records if r.category == "failed_to_resolve"
    )
    top_issues = [{"next_step": step, "count": n} for step, n in failed_steps.most_common(top)]

    # Popular new use-cases: out-of-scope requests (candidate features).
    new_use_cases = [
        {"conversation_id": r.conversation_id, "recommended_next_step": r.recommended_next_step}
        for r in records
        if r.category == "out_of_scope"
    ]

    negative = {"failed_to_resolve", "negative_feedback"}

    # Per-region health: total + how many went badly (which region has more issues).
    by_region: dict[str, dict] = {}
    for r in records:
        reg = r.region or "unknown"
        b = by_region.setdefault(reg, {"total": 0, "issues": 0})
        b["total"] += 1
        if r.category in negative:
            b["issues"] += 1

    # Which tenants have the most issues (tenant analytics — a company, not a person).
    tenant_issues: Counter = Counter()
    tenant_region: dict[str, str] = {}
    for r in records:
        if r.category in negative and r.tenant_id:
            tenant_issues[r.tenant_id] += 1
            tenant_region[r.tenant_id] = r.region or "unknown"
    top_tenants = [
        {"tenant_id": t, "region": tenant_region.get(t, "unknown"), "issues": n}
        for t, n in tenant_issues.most_common(top)
    ]

    return {
        "total_analysed": total,
        "category_distribution": distribution,
        "resolution_rate_pct": distribution["resolved"]["pct"],
        "failure_rate_pct": distribution["failed_to_resolve"]["pct"],
        "top_issues": top_issues,
        "new_use_cases": new_use_cases,
        "by_region": by_region,
        "top_tenants_by_issues": top_tenants,
        "unanalysed": store.unanalysed_count(),
    }
