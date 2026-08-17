# ADR-0018 — Enrich analysis with orchestrator context + LangSmith trace signals

**Status:** Accepted (2026-08-17)

## Context
The classifier previously saw only the chat transcript + a few deterministic signals + the
thumbs feedback. That is thin for judging `out_of_scope` vs `resolved` vs `failed_to_resolve`,
and it cannot detect knowledge-base gaps (JAI is a RAG assistant). Two rich, safe sources are
available read-only:

- The **JAI orchestrator** source (`jai-agent-orchestrator/src`) — its scope, tool/skill
  catalog, response settings, and **per-tenant scope rules** (e.g. UB: platform is "ShopBlue",
  four modules only, "eReq is outdated"). These decode what the assistant is *meant* to do.
- **LangSmith traces** (projects `uit_us/uit_eu/uit_uk`, joined by `metadata.conversation_id`)
  — router intent, retrieval hit/miss + retrieved doc names, agent used, response type, agent
  confidence, reasoning, frustration score, and errors.

A prior attempt to use LangSmith *as the transcript* produced garbage (raw prompt templates +
duplication polluted classification). The trace also carries secrets (a `_user_jwt_token` JWT,
`app_context` internal URLs) and user data that must never reach the LLM or our store.

## Decision
Feed both sources to the classifier (and the deep root-cause call) as **reference context, not
instructions**, behind a strict de-identification boundary (extends ADR-0007):

- **Orchestrator profile** — a *distilled*, secret-free summary of scope + tools + safe response
  settings + the RAG answering rules, plus the conversation's tenant rules. The 40 KB router
  prompt is **not** included verbatim (it is distilled) and only an allow-list of safe settings
  is read (never DB creds / service URLs / secret_manager). Read-only from `ORCH_SRC_PATH`;
  a compact built-in fallback is used if the source is absent.
- **LangSmith enrichment** — only an allow-list of safe fields is extracted; `run.extra.metadata`
  (where the JWT + app_context live) is never read. Every free-text field is PII +
  quasi-identifier scrubbed; user identity is pseudonymised (one-way hash), never sent raw.
- Both are wrapped as untrusted DATA (prompt-injection safe) and **only the scrubbed enrichment
  is stored**. **GCloud logs are never used.** Enrichment is best-effort: if LangSmith or the
  orchestrator source is unavailable, analysis is unchanged.

Config: `ENRICHMENT_ENABLED` (default on when a LangSmith key is present), `ORCH_SRC_PATH`,
`ORCH_PROFILE_ENABLED`, `ENRICHMENT_MAX_RUNS`; `LANGSMITH_API_KEY` (or `LANGSMITH_API_KEY_UIT`)
with per-region projects (`REGION_<X>_LANGSMITH_PROJECT`, default `uit_<region>`).

## Consequences
- Much better scope / resolution / knowledge-gap judgement (e.g. the UB "eReq" case is now
  understood as a scope-driven redirect rather than a blind failure).
- New privacy surface, mitigated by the scrubbing + secret allow-list above; a guard test fails
  if any JWT / URL / PII / quasi-identifier reaches the built prompt or the stored record.
- LangSmith cost/latency per conversation, bounded by `ENRICHMENT_MAX_RUNS`, a per-region
  project-id cache, and the best-effort skip; bounded by LangSmith's 15-day retention.
- Quasi-identifier scrubbing is tuned to blur identifier-like values (long reference codes,
  amounts, dates) without eating ordinary product/version terms (COVID-19, UTF-8, …).

## Alternatives considered
- **LangSmith as the transcript source** — rejected (previously polluted classification; the
  chat DB stays the canonical transcript).
- **Raw router system prompt in every request** — rejected (40 KB cost + pollution); distilled.
- **A committed snapshot of the orchestrator profile** — deferred; read live from `ORCH_SRC_PATH`
  with a built-in fallback, to avoid a stale copy of tenant rules.
