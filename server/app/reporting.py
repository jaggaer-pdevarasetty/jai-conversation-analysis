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

    return {
        "total_analysed": total,
        "category_distribution": distribution,
        "resolution_rate_pct": distribution["resolved"]["pct"],
        "failure_rate_pct": distribution["failed_to_resolve"]["pct"],
        "top_issues": top_issues,
        "new_use_cases": new_use_cases,
        "unanalysed": store.unanalysed_count(),
    }
