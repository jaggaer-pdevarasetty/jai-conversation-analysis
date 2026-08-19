# ADR-0020 — Environment toggle (UIT / PROD) with strict isolation

**Status:** Accepted (2026-08-18)

## Context
So far the app served a single environment (UIT): regional chat DBs configured via `REGIONS` /
`REGION_*`, LangSmith projects `uit_<region>`, and one results DB. We need reviewers to also
browse and analyse **PROD**, without mixing PROD and UIT results and without analysing PROD's
huge daily volume wholesale. Real PROD credentials aren't available yet, so PROD is initially
pointed at the UIT connection details (a dummy) to validate the whole system end to end.

## Decision
Add **environment** (`uit` default, `prod`) as a first-class axis orthogonal to region.

- **Config**: per-environment env vars via a `PROD_` prefix — `PROD_REGIONS`,
  `PROD_REGION_<R>_CHAT_DB_URL/_NAME/_SCHEMA`, `PROD_REGION_<R>_LANGSMITH_PROJECT`,
  `PROD_LANGSMITH_API_KEY`. `settings.regions(env)`, `langsmith_project_for(region, env)` (default
  `<env>_<region>`), `langsmith_api_key_for(env)`, `environments()`. UIT keeps the existing vars.
- **Selection**: every analysis endpoint accepts `?env=`; the client keeps the current env in one
  place and appends it to every request. A **UIT/PROD toggle** in the app bar persists the choice
  (remember-last) and reloads into that environment. PROD is visibly flagged (badge + colour).
- **Isolation**: the results store carries `environment` and its primary key is
  `(conversation_id, environment)`; every read/write/count filters by env. One results DB, but
  UIT and PROD can never collide or leak — even when they share conversation ids (as the dummy
  does). Existing rows are backfilled to `uit` by an idempotent startup migration.
- **Analysis is manual in both environments** (no boot/scheduled sweep). The **Analyze** flow is
  common — click → fetch new/unanalysed conversations — but PROD splits into two scopes:
  - **UIT**: one list of new/unanalysed conversations + a single **Start analysis** (scope=all).
  - **PROD**: two sections, each with its own button — **Analyze feedback** (`scope=feedback`,
    conversations that have user feedback) and **Analyze all** (`scope=all`, every conversation,
    shown with a warning that it includes the feedback ones). Conversations can also be analysed
    one at a time from the conversation list. `lazy_analyze` (auto-analyse on open) stays UIT-only.
  - *(One-time)* existing PROD feedback conversations were seeded into the store; going forward all
    PROD analysis is user-triggered by those buttons.
- **Separate queues per environment**: one `AnalysisQueue` instance backs both, but items are
  `(env, conversation_id)` and the `/queue` view + counts are filtered by `env`, so the UIT live
  queue never shows PROD work and vice-versa; a sweep in one env never appears in the other.
- **Guards carry over**: PII/quasi-identifier scrubbing, prompt-injection safety, empty-transcript
  skip, read-only SELECT-only access, dedup/retry/dead-letter, per-conversation daily cap.

## Consequences
- Reviewers switch environments from the UI; PROD data stays separate and is analysed only
  deliberately, bounding LLM cost against PROD's volume.
- Security/compliance to complete when real PROD lands: a dedicated read-only PROD credential,
  RBAC gating for PROD, EU data-residency for the LLM + results DB, and an audit log of env
  switches / PROD analyse triggers. (Privacy stays **admin** per the product decision.)
- Supersedes the single-environment assumptions in ADR-0001/0009 (adds the env dimension).

## Alternatives considered
- **Separate results DB per environment** — stronger physical isolation but more infra +
  connection routing; rejected in favour of one DB + a composite key + mandatory env filter.
- **Analyse all PROD conversations** — rejected: far too costly at PROD volume; feedback-only
  bulk + on-demand per-conversation is the posture.
- **Header (`X-Environment`) instead of `?env=`** — rejected: a query param mirrors the existing
  `?region=`, is cacheable and easy to test.
