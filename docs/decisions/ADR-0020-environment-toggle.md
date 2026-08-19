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
- **PROD analysis posture** (volume-aware):
  - Browse everything (dashboard/tenants/conversations) straight from the PROD chat DB — no
    analysis required.
  - **Conversations WITH user feedback are auto-analysed** (no per-item permission): existing
    ones "till now" via a background sweep on a FastAPI **startup event**, and any new ones when a
    reviewer clicks **Analyze** (which, in PROD, fetches + starts immediately — no confirmation).
    Bulk analysis in PROD is always **feedback-only**.
  - **Conversations WITHOUT feedback are analysed only on demand** — the reviewer clicks the
    **per-conversation Analyze** button. General `lazy_analyze` (auto-analyse on open) stays
    **UIT-only**, so browsing PROD never analyses its huge no-feedback volume.
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
