# ADR-0017 — Feedback review frontend on the existing API

**Status:** Accepted (2026-08-11)

## Context
Feedback is a critical reviewer workflow. The existing `/feedback` API returns explicit ratings,
source metadata, analysis, telemetry, and optional deep analysis; `/conversations/{id}` returns the
full transcript. It does not expose a dedicated feedback-detail endpoint or the exact source
`feedback.message_id`. Server ownership is assigned to another agent, so this change is frontend-only.

## Options considered
1. **Wait for a new server contract.** Exact message highlighting, but blocks the important UI.
2. **Compose the existing endpoints with an honest fallback.** Ships the complete review workflow
   now and never presents inferred context as an exact match.
3. **Assume the final assistant response is exact.** Visually simple but creates false data.

## Decision
Choose option 2. `/feedback` becomes an analytics table with rating/category/search/sort filters,
summary metrics, root-cause previews, source context, telemetry, and pagination. `/feedback/[id]`
combines the existing feedback item and conversation detail response into a full transcript,
feedback remark, deep analysis, recommendation, rationale, source context, and telemetry view.

Use `feedback_message_id` or `feedback.message_id` when the API supplies one. Until then, highlight
the final assistant response only as **Feedback context** and show an explicit notice that the exact
rated-message ID is unavailable.

## Server-agent request
Add `GET /api/analysis/feedback/{conversation_id}` or extend conversation detail with
`feedback.message_id`. The response should include source metadata, ordered messages, feedback,
analysis, deep analysis, and metrics. The feedback-list endpoint should eventually support
rating/category/query/sort/limit/offset so frontend filtering remains correct at scale.

## Consequences
- The important feedback workflow ships without modifying server-owned files.
- Current API values are displayed directly; unavailable data is labelled rather than fabricated.
- Exact rated-message highlighting activates automatically when the server adds the optional ID.
