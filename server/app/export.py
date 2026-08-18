"""Feedback export — full detail per feedback conversation, as CSV / JSON / PDF.

Includes everything a reviewer needs offline: category + confidence, feedback type + user remark,
the three-part root-cause analysis (what happened / why / how to avoid), suggestions +
recommended action, cost & responsiveness metrics, source metadata, and the FULL de-identified
transcript (as JSON). All conversation text is already PII-scrubbed in the store.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone

_NEGATIVE = {"failed_to_resolve", "negative_feedback"}
_SEARCH_FIELDS = (
    "conversation_id", "user_remark", "title", "tenant_name", "user_name",
    "recommended_next_step", "why_it_happened",
)

# Flat columns (transcript is added separately per format).
FIELDS = [
    "conversation_id", "region", "tenant_id", "tenant_name", "user_name", "title",
    "last_message_at", "analyzed_at", "feedback_type", "user_remark",
    "category", "model_category", "confidence", "override_category", "rationale",
    "what_happened", "why_it_happened", "how_to_avoid", "suggestions", "recommended_next_step",
    "ttft_ms", "input_tokens", "output_tokens", "prompt_tokens",
    "analyzer_version", "run_id",
]


def collect_rows(store, scope: str = "all", region: str | None = None,
                 rating: str | None = None, category: str | None = None, *,
                 query: str | None = None, tenant: str | None = None,
                 date_range: str | None = None, date_from=None, date_to=None,
                 sort: str = "newest") -> list[dict]:
    """All feedback conversations in scope (no pagination), each with full detail + transcript.

    Honours the SAME filters as GET /feedback (search text, tenant, activity date range, sort) so
    a download matches exactly what the reviewer has on screen.
    """
    records = store.list(region=region)
    convs = store.get_conversations([r.conversation_id for r in records])
    try:
        from . import dashboard
        meta = dashboard.conversation_meta([r.conversation_id for r in records], region=region)
    except Exception:  # noqa: BLE001 - chat DB metadata is best-effort
        meta = {}

    rows: list[dict] = []
    for rec in records:
        conv = convs.get(rec.conversation_id)
        rating_val = conv.feedback.rating if conv else None
        has_thumbs = rating_val is not None
        neg_outcome = rec.category in _NEGATIVE
        if scope == "thumbs" and not has_thumbs:
            continue
        if scope == "outcomes" and not neg_outcome:
            continue
        if scope == "all" and not (has_thumbs or neg_outcome):
            continue
        if rating and (rating_val is (rating == "positive")) is False:
            continue
        if category and rec.category != category:
            continue

        deep = rec.deep
        m = rec.metrics
        md = meta.get(rec.conversation_id, {})
        transcript = [
            {"sequence_num": msg.sequence_num, "role": msg.role, "content": msg.content}
            for msg in (conv.messages if conv else [])
        ]
        rows.append({
            "conversation_id": rec.conversation_id,
            "region": rec.region or md.get("region"),
            "tenant_id": rec.tenant_id or md.get("tenant_id"),
            "tenant_name": md.get("tenant_name"),
            "user_name": md.get("user_name"),
            "title": md.get("title"),
            "last_message_at": md.get("last_message_at"),
            "analyzed_at": rec.analyzed_at,
            "feedback_type": (
                "thumbs_up" if rating_val is True else "thumbs_down" if rating_val is False else "none"
            ),
            "user_remark": (conv.feedback.comment if conv else None) or (deep.user_remark if deep else "") or "",
            "category": rec.category,
            "model_category": rec.model_category,
            "confidence": rec.confidence,
            "override_category": rec.override.category if rec.override else None,
            "rationale": rec.rationale,
            "what_happened": deep.what_happened if deep else "",
            "why_it_happened": deep.why_it_happened if deep else "",
            "how_to_avoid": deep.how_to_avoid if deep else "",
            "suggestions": deep.suggestions if deep else "",
            "recommended_next_step": rec.recommended_next_step,
            "ttft_ms": m.ttft_ms,
            "input_tokens": m.input_tokens,
            "output_tokens": m.output_tokens,
            "prompt_tokens": m.prompt_tokens,
            "analyzer_version": rec.analyzer_version,
            "run_id": rec.run_id,
            "transcript": transcript,
        })

    # --- same text / tenant / date / sort filters as GET /feedback ---
    tq = (query or "").strip().lower()
    if tq:
        rows = [r for r in rows if any(tq in str(r.get(f) or "").lower() for f in _SEARCH_FIELDS)]
    tn = (tenant or "").strip().lower()
    if tn:
        rows = [r for r in rows if tn in str(r.get("tenant_name") or "").lower()]

    range_start, range_end = date_from, date_to
    if date_range:
        range_end = datetime.now(timezone.utc).date()
        range_start = range_end - timedelta(days=6 if date_range == "last_7_days" else 29)
    if range_start or range_end:
        def _day(r):
            value = r.get("last_message_at") or r.get("analyzed_at")
            if not value:
                return None
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
            except (ValueError, TypeError):
                return None

        rows = [
            r for r in rows
            if (d := _day(r)) is not None
            and (range_start is None or d >= range_start)
            and (range_end is None or d <= range_end)
        ]

    if sort == "oldest":
        rows.sort(key=lambda r: r.get("last_message_at") or r.get("analyzed_at") or "")
    elif sort == "negative_first":
        def _rank(r):
            if r["feedback_type"] == "thumbs_down":
                return 0
            if r["category"] in _NEGATIVE:
                return 1
            if r["feedback_type"] == "thumbs_up":
                return 2
            return 3
        rows.sort(key=_rank)
    else:  # newest
        rows.sort(key=lambda r: r.get("last_message_at") or r.get("analyzed_at") or "", reverse=True)
    return rows


def to_json(rows: list[dict]) -> bytes:
    return json.dumps(rows, indent=2, default=str).encode("utf-8")


def to_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[*FIELDS, "transcript_json"], extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        flat = {k: r.get(k) for k in FIELDS}
        flat["transcript_json"] = json.dumps(r.get("transcript", []), default=str)
        writer.writerow(flat)
    return buf.getvalue().encode("utf-8")


def _latin1(s) -> str:
    # fpdf2 core fonts are latin-1; replace unsupported chars so non-English text can't crash the
    # PDF (CSV/JSON keep full Unicode). Values shown as-is otherwise.
    return ("" if s is None else str(s)).encode("latin-1", "replace").decode("latin-1")


def to_pdf(rows: list[dict]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    def cell(text: str, size: int = 10, bold: bool = False) -> None:
        pdf.set_font("helvetica", "B" if bold else "", size)
        # new_x=LMARGIN resets the cursor to the left margin (fpdf2 defaults to RIGHT, which
        # would leave zero width for the next full-width cell); wrapmode CHAR breaks long tokens.
        pdf.multi_cell(0, 5, _latin1(text), new_x="LMARGIN", new_y="NEXT", wrapmode="CHAR")

    if not rows:
        pdf.add_page()
        cell("No feedback conversations for the selected filters.", 12)
        return bytes(pdf.output())

    def field(label: str, value) -> None:
        cell(label, 10, bold=True)
        cell(value if value not in (None, "") else "-", 10)
        pdf.ln(1)

    for r in rows:
        pdf.add_page()
        cell(str(r.get("title") or r["conversation_id"]), 13, bold=True)
        cell(
            f"{r['conversation_id']}  |  region: {r.get('region')}  |  tenant: "
            f"{r.get('tenant_name') or r.get('tenant_id')}  |  {r.get('last_message_at') or ''}",
            9,
        )
        pdf.ln(2)
        field("Feedback", f"{r['feedback_type']}   remark: {r.get('user_remark') or '-'}")
        field("Category / Confidence", f"{r['category']} ({r['confidence']})"
              + (f"  [overridden -> {r['override_category']}]" if r.get("override_category") else ""))
        field("What happened", r.get("what_happened"))
        field("Why it happened (root cause)", r.get("why_it_happened"))
        field("How to avoid", r.get("how_to_avoid"))
        field("Suggestions", r.get("suggestions"))
        field("Recommended next step", r.get("recommended_next_step"))
        field("Cost & responsiveness",
              f"TTFT {r.get('ttft_ms')} ms | tokens in {r.get('input_tokens')} / "
              f"out {r.get('output_tokens')} / prompt {r.get('prompt_tokens')}")
        cell("Transcript", 10, bold=True)
        for msg in r.get("transcript", []):
            cell(f"{msg['role']}: {msg['content']}", 9)
            pdf.ln(0.5)
    return bytes(pdf.output())


def render(rows: list[dict], fmt: str) -> tuple[bytes, str]:
    """Return (bytes, media_type) for the requested format."""
    if fmt == "json":
        return to_json(rows), "application/json"
    if fmt == "pdf":
        return to_pdf(rows), "application/pdf"
    return to_csv(rows), "text/csv"
