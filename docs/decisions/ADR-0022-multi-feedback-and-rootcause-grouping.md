# ADR-0022 — Capture all feedback per conversation + root-cause/knowledge-gap grouping with impact ranking

**Status:** Accepted (2026-08-21)

## Context
Two gaps limit reviewer effectiveness:

1. **One feedback per conversation.** Ingest keeps only the first feedback it finds
   (`chatdb.py`: `if fb and conv_feedback.rating is None: ...`), so a conversation rated on more
   than one turn loses the rest. Real example: `ba596973` (user rmaddox) has a thumbs‑down on the
   *supplier* turn AND on the *"services → Services form"* turn; only the first was stored/analysed.
2. **No way to see recurring problems.** Every failed conversation is reviewed one at a time, even
   though many fail for the same underlying reason (e.g. the same document not retrieved). There is
   no grouping or impact ranking to let a reviewer fix once and resolve many.

Constraints: the common store is de‑identified (ADR‑0007) — conversation_id only, `tenant_id`
kept (a company), **no user identity**. Enrichment already pseudonymises user identity one‑way
(ADR‑0018). `enrichment.retrieval_hit == False` is a deterministic knowledge‑gap signal.

## Decision

### Part A — capture all feedback
- Add `feedbacks: list[Feedback]` to `Conversation` and `CommonConversation` (additive; the single
  `feedback` stays as the primary for back‑compat). Ingest collects **every** feedback per chat,
  each tied to its `message_id`. De‑identification scrubs each; storage is a JSON column
  (`asdict`) so old rows rehydrate via a back‑compat default (`data.get("feedbacks")` or
  `[feedback]`) — no DB migration. The deep (Tier‑2) analysis considers all feedbacks.

### Part B — root cause + grouping + impact
- Add a structured `root_cause` enum to `DeepAnalysis` (LLM picks: `knowledge_gap`,
  `wrong_document_retrieved`, `wrong_routing`, `ambiguous_question`, `tool_error`,
  `missing_tenant_rule`, `other`). Records without a label fall back deterministically to
  `knowledge_gap` when `enrichment.retrieval_hit == False`. Labels are enums only (no PII).
- New `GET /api/analysis/groups`: buckets analysed records by `root_cause` and returns, per group,
  **conversations**, **tenants** (distinct `tenant_id`) and **users** (distinct `user_hash`)
  counts, sorted by impact. A new **Insights** page lists impact‑ranked groups and drills into the
  feedback list filtered by `root_cause`.

### Compliant user‑impact counts
- Add `user_hash: str` to `AnalysisRecord`, set from the source `user_id` via
  `pii.pseudonymize("user", user_id)` — a non‑reversible one‑way hash. Distinct‑user impact is
  counted from `user_hash`; **no raw user identity is stored** and a user cannot be resolved from
  the pooled area. `/groups` returns **aggregate counts only** (no tenant/user identity).

## Consequences
- Multi‑turn feedback is never lost; the deep analysis sees the full picture.
- Reviewers get a "fix once, resolve many" view ranked by real impact (conversations/tenants/users).
- Existing records need a **re‑analysis** to populate `feedbacks`, `user_hash`, and `root_cause`;
  old rows keep working via back‑compat defaults in the meantime.
- New pseudonym is one‑way; de‑identification boundary (ADR‑0007) and the enrichment secret/PII
  guard (ADR‑0018/0021) are preserved.

## Alternatives considered
- **Replace `feedback` with `feedbacks`** — rejected (breaks back‑compat + more churn; additive is safer).
- **User counts via a live chat‑DB lookup per group** — rejected (heavier + touches source identity);
  the stored one‑way pseudonym is accurate, cheaper, and compliant.
- **Deterministic‑only root cause** — rejected as primary (coarser); kept as the fallback.
- **Two separate PRs** — combined into one per product decision.
