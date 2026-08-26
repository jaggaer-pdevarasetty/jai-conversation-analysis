# ADR-0021 — Two-tier analysis + richer (PII-scrubbed) LangSmith evidence

**Status:** Accepted (2026-08-21)

## Context
Analysis today (ADR-0010/0018) gives each conversation one classifier pass (category, next step,
confidence, rationale) plus, for feedback conversations, one deeper root-cause pass. It already
consumes a **scrubbed allow-list** of LangSmith signals and the orchestrator profile/tenant rules,
and stores only that scrubbed subset — never the raw trace (which carries a `_user_jwt_token`,
`app_context`, internal URLs, and raw user/tenant identity).

Reviewers need (a) to see **what the live agent was thinking** on every conversation, (b) a much
sharper picture on **feedback** conversations (the ones users complained about), and (c) to fix
issues **faster**. Two richer trace fields are available but were intentionally excluded so far:
the **retrieved-document snippets** (in the root run's `citations[].snippet`) and the **actual
invocation prompt** (system + assembled context, in the LLM child run). Both can contain customer
PII. Product decision: we may use/store them **provided PII is removed** and **secrets are never
touched**. LangSmith retains only ~**15 days**, so trace evidence exists for recent conversations
only.

## Decision
Formalise **two analysis tiers**, both behind the existing de-identification boundary (extends
ADR-0007 / ADR-0018):

- **Tier 1 — Standard analysis (ALL conversations):** transcript + chat telemetry + the scrubbed
  LangSmith signals, **plus the agent's own reasoning** ("model thinking") surfaced on every
  conversation. Output unchanged (category/step/confidence/rationale) + stored `agent_reasoning`.
- **Tier 2 — Aggressive / feedback analysis (conversations WITH user feedback):** everything in
  Tier 1 **plus the PII-scrubbed retrieved-document snippets and the PII-scrubbed actual
  invocation prompt**, fed into the deep root-cause pass for maximum accuracy. Also **capture
  ALL feedback on a conversation** (previously only one was kept, so multi-turn feedback was
  missed).

**Evidence handling (hard rules):**
1. **Secrets are never fetched or stored** — `run.extra` / `_user_jwt_token` / `app_context` /
   internal URLs / raw user_id / email / tenant name. (Unchanged from ADR-0018; non-negotiable.)
2. **Snippets and the invocation prompt are PII + quasi-identifier scrubbed** via `pii.redact`
   before they are stored or shown, and **size-bounded** (`SNIPPET_MAX_CHARS`, `PROMPT_MAX_CHARS`).
3. **Only the scrubbed, allow-listed result is persisted** (extends the `Enrichment` record with
   `agent_reasoning`, `retrieved_snippets`, `invocation_prompt`). The raw trace is never persisted.
4. A **compliance guard test** fails the build if any JWT/URL/id/email/secret appears in the
   stored record (extended to the new fields).
5. **Time-bounded:** trace-derived fields fill in only for conversations inside LangSmith's ~15-day
   window; older conversations keep transcript-only analysis. New conversations enrich going forward.

**UI:** surface the scrubbed LangSmith signals + agent reasoning on every conversation; a richer
feedback view (scrubbed prompt + snippets + separated what/why/how/suggestions); and **root-cause /
knowledge-gap grouping** with impact count + a deep-link to the LangSmith trace, to speed triage.

Config: `ENRICH_SNIPPETS`, `ENRICH_PROMPT` (feedback only), `SNIPPET_MAX_CHARS`, `PROMPT_MAX_CHARS`.

## Consequences
- Sharper `out_of_scope` / `failed_to_resolve` / knowledge-gap judgement and, for feedback, a
  root cause grounded in the exact retrieved context — like the rmaddox "Services form" case.
- **New PII surface** (snippets + prompt) mitigated by mandatory scrubbing + secret allow-list +
  the guard test; residual scrubber imperfection is an accepted, reviewed trade-off.
- Multi-feedback capture means a conversation can carry more than one feedback item.
- **EU data residency (GDPR):** storing EU-derived snippets/prompt in a US results DB must be
  reviewed before real PROD EU data (flagged, consistent with ADR-0020).
- GCP/GCloud logs remain **out of scope** (no access + security).

## Alternatives considered
- **Store the raw LangSmith trace** — rejected (JWT/URLs/PII; breaks ADR-0007 + a security risk).
- **Keep snippets/prompt out entirely** — rejected (product wants the extra accuracy; scrubbing
  makes it acceptable).
- **Use GCloud logs for ground truth** — rejected (no access; security).
