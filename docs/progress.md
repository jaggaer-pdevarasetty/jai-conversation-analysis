# Progress

_Last updated: 2026-08-11_

## Current state
**Working prototype scaffold, tests green on both sides**, running on mock fixtures.
Source of truth confirmed as **J1-93353** (ADR-0005). Stack = **Next.js client + FastAPI
server** (ADR-0006). Real chat-DB / LangSmith / Gemini wiring is gated on credentials.

## Done
- Deep analysis of both org repos; confirmed correlation (`conversation_id==thread_id`,
  `message_id→run_id`), LangSmith metadata, 15-day retention, FR-4 metric gaps.
- PM confirmed: **J1-93353 source of truth; all conversations; data from LangSmith + DB**.
- Repo restructured to `client/` (Next.js) + `server/` (FastAPI), mirroring jai-agentos-chat.
- **server/**: FastAPI read API (`/api/analysis/conversations[/{id}]`), domain
  (signals/category/analyze), in-memory store, RFC 7807, LangSmith client. **20 pytest
  tests green (~0.2s)** — unit + TestClient integration + boundary-mocked LangSmith +
  OpenAPI-3.1 assertion.
- **client/**: Next.js + MUI reviewer UI (`ReviewerTable`) + services layer. **2 jest
  tests green (~0.8s)** with Testing-Library (`getByRole`/`getByLabelText`); typecheck clean.
  Next bumped to **15.5.23** (patched CVE-2025-66478).
- Governance current: AGENTS.md, .windsurfrules (5 rules), docs 01–08, ADR-0001..0006,
  session log, `api/openapi.yaml`. CLAUDE.md + .cursorrules removed per direction.
- CI wired (`.github/workflows/ci.yml`): client (lint/typecheck/jest) + server (pytest +
  OpenAPI contract on PR) + gitleaks.

## Ticket update (2026-08-11)
J1-93353 was expanded into a full PRD (FR-1..4 + NFRs + AC-1..11). New/changed
requirements now captured in `03-prd.md` / `06-nfr-slos.md` / `05-architecture.md`:
manual analysis trigger (eligible after 5-min inactivity; ADR-0019), **de-identification +
conversation-ID-only attribution** (ADR-0007), pooled RBAC, retry + visible unanalysed
count (ADR-0008), telemetry-missing-not-zero, human override (audited), ≥85% accuracy,
non-English handling. Working on branch **`feature/J1-93353-conversation-analysis`**
(cut per the Branching Strategy; no pushes to protected branches).

## Done — execution increment 1 (branch feature/J1-93353-conversation-analysis)
- **Phase 1 (ADR-0007):** common store + API are now **conversation-ID-only**; tenant/user
  dropped; de-identification boundary (`server/app/deidentify.py`) scrubs content before the
  common store. Tests assert **no tenant/user leakage** (AC-10).
- **Phase 2 (ADR-0008):** eligibility (inactive ≥5 min, AC-11) + run tracking + **retry** +
  **visible unanalysed count** (AC-9) in `server/app/run.py`.
- **Phase 5:** human **override + audit** (effective vs model category) endpoint.
- **Phase 0:** `api/openapi.yaml` updated (no tenant; metrics; status; override; runs).
- **Telemetry** rendered as **unavailable, not zero** (AC-7); **non-English** categorised
  (AC-8). Client updated (no tenant; unavailable rendering; unanalysed banner).
- Tests green: **server 32 pytest**, **client 4 jest + tsc + lint**.

## Done — execution increment 2
- **Gemini classifier** (ADR-0010): real AI classification via REST when `GEMINI_API_KEY`
  is set; deterministic rules fallback; raises on API failure → retry (AC-9); non-English
  (AC-8); prompt-injection-safe. Mocked tests.
- **Persistent store** (ADR-0009): `SqlResultStore` (SQLAlchemy) — **SQLite by default**,
  **Postgres via `docker-compose.postgres.yml`** + `RESULTS_DB_URL`. `STORE_BACKEND` switch.
  Verified end-to-end (data persisted to a real DB file).
- **Local pre-commit hook** (`.git/hooks/pre-commit`, untracked/never pushed): runs server
  pytest + client typecheck/lint/jest; blocks commit on failure.
- Tests green: **server 39 pytest**, **client 4 jest + tsc + lint**.

## Done — execution increment 3 (env, Vertex, Postgres, Zscaler)
- **.env loading fixed** — loads repo-root `.env`; tests hermetic (`DOTENV_DISABLE` + conftest).
- **Vertex-only classifier** (ADR-0010): provided key confirmed unusable (Vertex rejects API
  keys → needs SA/ADC + project + location). Uses google-genai Vertex mode; **falls back to
  rules when Vertex isn't configured** so the UI is never blank.
- **Postgres-only persistence** (ADR-0009): SQLite dropped; runs `postgres:16-alpine` via
  **podman** (Docker absent) on `:5433`; store + tests verified against real Postgres.
- **Zscaler-safe HTTP** (`app/http.py`): env CA (`REQUESTS_CA_BUNDLE`) + proxy (`HTTPS_PROXY`);
  TLS never disabled.
- Verified end-to-end: rules fallback → 6 analysed, 6 rows persisted in Postgres. **39 pytest green.**

## Done — execution increment 4 (Vertex live + eval harness)
- **Vertex confirmed WORKING** in `us-central1` via gcloud **ADC** (project
  `gcp-jai-platform-dev`) — 6/6 fixtures classified by `vertex:gemini-2.5-flash`, persisted
  to Postgres. Enable in-app by adding project+location+`STORE_BACKEND=sql` to `.env` + restart.
- **Classifier prompt tuned** — explicit thumbs feedback now wins → positive/negative_feedback.
- **Eval harness** (ADR-0011): agreement % + confusion matrix + **resolved-mislabel hard
  gate**; `python -m app.eval`. Rules baseline 100%; **live Vertex eval 100%** on the fixture
  gold set. Tests green: **server 42 pytest**.

## Done — execution increment 5 (LangSmith-as-source)
- **LangSmith source built** (ADR-0012): `SOURCE=langsmith` pulls runs from project
  `jai-orchestrator`, groups by conversation_id → Conversation (messages best-effort;
  tokens/latency authoritative); env-aware client (Zscaler CA/proxy); startup fails safe.
  Mock-tested (45 pytest green). Selector `SOURCE=fixtures|langsmith` (default fixtures).
- **DB check:** Postgres reachable (`localhost:5433/analysis`); **but `.env` still has
  STORE_BACKEND=memory** → add `STORE_BACKEND=sql` to persist there.
- **LangSmith live status:** from this machine → `CERTIFICATE_VERIFY_FAILED` (Zscaler).
  Fix locally by setting `REQUESTS_CA_BUNDLE`=Zscaler root CA (TLS never disabled), or run
  in GCP. No code blocker.

## Done — execution increment 6 (real LangSmith data, live-confirmed)
- **Zscaler TLS solved** via `truststore` (OS trust store) — no TLS disabling. `app/http.py`
  prefers an explicit CA file, else OS store, else certifi.
- **LangSmith live-confirmed**: real projects are `prelogin_uit | uit_us | uit_eu | uit_uk`
  (the `.env` had a wrong `jai-orchestrator`). End-to-end with `SOURCE=langsmith`
  project=prelogin_uit → **12 real conversations analysed → 12 rows persisted in Postgres**,
  0 failures.
- **Bug fixed** (found via real data): LangSmith timestamps are tz-naive → normalise to UTC
  in `run.py` (eligibility no longer crashes). Regression test added. **46 pytest green.**

## Done — execution increment 7 (REAL chat DB, correctness fixes)
- **Root-cause + fix:** LangSmith-as-source produced garbage (duplicated text + prompt
  templates) → everything `failed_to_resolve`. Built `app/chatdb.py` — **READ-ONLY** reader
  of the real chat DB schema `jai_agentos_schema_uit` (db `jai_agentos_uit`):
  conversations/messages/feedback/token_usage. `SOURCE=chatdb` is now canonical.
- **Verified correct**: 10 real conversations → varied categories via Vertex
  (resolved / failed_to_resolve / out_of_scope) + real next steps + authoritative tokens.
- **UI-empty fixed**: CORS only allowed `localhost:3000`; widened to any localhost/127.0.0.1
  port (browser previews were blocked).
- **Tests never touch the app DB**: SQL-store tests skip unless `TEST_DATABASE_URL` is set
  (45 pass, 3 skip). Dropped the `analysis_test` DB I mistakenly created; deleted the pem.
- **Pagination + 429 backoff** for LangSmith (kept for token enrichment only).
- Facts: results store = **podman Postgres** `localhost:5433/analysis` (NOT sqlite).

## Done — execution increment 8 (reviewer UI/UX rewrite)
- **Reviewer-first UI** (ADR-0013): replaced the source-identity overview with a pooled health
  dashboard built from analysis + latest-run data; primary navigation is now health → queue → review.
- **Health overview:** outcome mix, positive/attention rates, telemetry completeness, run status,
  retry visibility, review signals, and recent analyses without requiring the live chat DB.
- **Review queue:** ID/action search, category + confidence filters, priority/newest/confidence sort,
  explicit loading/error/empty states, human-override and feedback indicators, formatted telemetry.
- **Conversation review:** transcript-first layout with model evidence/signals, recommendation,
  feedback, complete token/TTFT telemetry, run/analyzer audit metadata, and audited override control.
- **Responsive/accessibility:** mobile drawer, no page-level horizontal overflow at 375px, labelled
  controls and status regions. Verified against 51 live local records with no browser runtime errors.
- Green: **client 9 jest + typecheck + lint + production build; server 47 pytest, 3 skipped**.

## Done — execution increment 9 (tenant-first workspace correction)
- **Tenant-first routing** (ADR-0014, supersedes ADR-0013 landing decision): `/` redirects to
  `/tenants`; Health overview was removed; primary navigation now exposes Tenants + Review queue.
- **Tenant directory:** name/ID search, tenant/user/conversation totals, responsive organisation
  cards, and explicit loading/error/empty states.
- **Tenant users:** tenant context, role filtering, user search, volume summaries, and direct
  user-conversation routing.
- **User conversations:** tenant/user breadcrumbs, analysis progress, outcome/status filtering,
  message and analysis counts, lazy-analysis refresh, and safe review links only after analysis.
- **Scope clarity:** tenant pages are labelled Authorised admin view; pooled conversation routes
  remain separately labelled De-identified review.
- Green: **client 10 jest + typecheck + lint + clean production build; server 49 pytest, 3 skipped**.
  Browser-checked tenant directory and users at desktop/mobile widths with no runtime errors or overflow.

## Done — execution increment 10 (Overview restored by product clarification)
- Restored `/` as **Overview** and added Overview + Tenants + Review queue to primary navigation.
- Overview combines aggregate tenant/user/source counts with analysis coverage, outcome distribution,
  telemetry completeness, retry health, latest-run details, review signals, and recent records.
- Tenant administration remains unchanged at `/tenants`; shell labels distinguish operational,
  authorised-admin, and de-identified scopes.
- Green after an isolated cache rebuild: **client 10 jest + typecheck + lint + production build;
  server 49 pytest, 3 skipped**. Overview browser-check passed at desktop/mobile widths.

## Done — execution increment 11 (Markdown + filter/UI fixes)
- Chat messages, recommendations, and rationale now render safe styled Markdown (bold/italic,
  headings, lists, links, code, quotes) as React nodes; raw HTML and unsafe links are not executed.
- Replaced every overlapping native select with responsive MUI selects across queue and tenant pages.
- Added queue review-state filters (attention, feedback, overrides, missing telemetry) and latency/token
  sorting; verified zero filter overlap at 1024px and no page overflow at 375px.
- Green: **client 11 jest + typecheck + lint + production build; server 52 pytest, 3 skipped**.
  Real transcript check: 14 strong elements, 2 rendered lists, no raw `**`, no runtime errors.

## Done — execution increment 12 (pagination + live queue)
- Pooled review queue now uses server-owned search, filters, sorting, `limit`/`offset`, filtered
  totals, page-size controls, and correct page requests across all 299 current analyses.
- Added a live queue panel polling every 3s; it displays real queued/analysing/retrying conversation
  IDs, attempts, enqueue times, depth, workers, dead-letter count, idle/inactive states, and pages.
- Added pagination to the 53-tenant directory and SQL-backed user conversation histories.
- Green: **client 13 jest + typecheck + lint + production build; server 58 pytest, 3 skipped**.
  Browser-verified queue and tenant pagination with no runtime errors or horizontal overflow.

## Done — execution increment 13 (feedback analytics frontend)
- Rebuilt `/feedback` as a responsive analytics table with explicit-rating totals, sentiment and
  deep-analysis coverage, negative-priority alerting, search/category/sentiment/sort filters,
  root-cause previews, source context, telemetry, and local pagination.
- Added `/feedback/[id]`: full ordered Markdown transcript, prominent user remark, category and
  confidence, root-cause sections, remediation guidance, source metadata, and complete telemetry.
- Exact `feedback_message_id` is used automatically when available; the current API lacks it, so the
  final assistant response is labelled **Feedback context** with an explicit non-exact notice.
- Fixed Overview recent-row overlap: UUID/date are separate block lines, narrow content uses two
  columns, and category/recommendation appear only when the post-sidebar width is sufficient.
- Frontend only: **14 jest + typecheck + lint + production build**. No server-owned files changed.

## Done — execution increment 14 (frontend correctness, latency, and CI)
- Removed the MUI SSR warning from Markdown rendering by replacing the unsafe first-child selector;
  added a server-render regression test.
- Region changes now persist the selection, return to `/`, and load Overview with the selected
  region. Data pages wait for saved-region restoration instead of issuing a duplicate all-region request.
- Removed SQL result-store N+1 reads with a bulk conversation lookup; dashboard engines now reuse
  pooled connections. Measured bulk loading of 2,959 conversations improved from ~3.3s to ~0.12s;
  warm overview from ~5.1s to ~1.1s and metadata from ~6.9s to ~1.8s.
- Feedback filtering, sorting, search, and pagination moved to the API (spec first), so normal page
  loads enrich and return only the requested rows instead of transferring the full ~458 KB dataset.
- Fixed the GitHub gitleaks check after its action began requiring `GITHUB_TOKEN` for PR scans.
- Green: **client 17 jest + typecheck + lint + production build; server 77 pytest, 3 skipped;
  OpenAPI/workflow YAML valid; read-only posture guard passed**.

## Done — execution increment 15 (activity dates, filters, Markdown, ID search)
- Feedback and conversation tables now default to newest **conversation activity** rather than
  analysis-run time; both expose newest/oldest activity options and label last-message versus analysis dates.
- Database timestamps are returned in ISO format, feedback filter requests show visible progress, and
  live checks confirmed newest ordering plus the negative-rating filter.
- Feedback remarks and root-cause text now use the safe Markdown renderer in both list and detail views.
- Overview now includes direct navigation by conversation UUID or tenant ID.
- Green: **client 22 jest + typecheck + lint + production build; server 81 pytest, 3 skipped;
  OpenAPI YAML valid; read-only posture guard passed**.

## Done — execution increment 16 (whole-frontend UI/UX audit)
- Fixed the blank All-regions selector with explicit empty-value rendering, a real combobox label,
  loading/disabled state, and fallback when a saved region becomes unreachable.
- Prevented small-screen app-bar/search overflow, validated overview ID searches, guarded stale overview
  and detail responses, and added retry actions to both conversation detail experiences.
- Rendered remaining recommendation fields as safe Markdown; clarified unfiltered empty states, added
  keyboard focus treatment, explicit table scrolling, and announced loading states to assistive technology.
- Audited every frontend route and restarted the dev server only after a clean production build.
- Green: **client 24 jest + typecheck + lint + production build**; all eight frontend routes return 200.

## Done — execution increment 19 (environment toggle: UIT / PROD)
- Added an **environment** axis (uit/prod) orthogonal to region (ADR-0020). A UIT/PROD toggle in
  the app bar (remember-last) switches the whole app; every request carries `?env=`.
- **Strict isolation**: results store now keyed by `(conversation_id, environment)` with an
  idempotent startup migration (existing rows → uit); every read/write/count filters by env.
- **PROD posture** (manual, no auto/boot sweep): the **Analyze** dialog splits into two scopes —
  **Analyze feedback** (`scope=feedback`) and **Analyze all** (`scope=all`, warned it includes
  feedback); conversations can also be analysed one at a time. UIT keeps the single-list dialog.
  Existing PROD feedback was seeded once; future PROD analysis is user-triggered. lazy-analyse UIT-only.
- **Separate queues per env**: `/queue?env=` is filtered by environment (items + counts), so the UIT
  live queue never shows PROD work and vice-versa (one queue instance, `(env, id)` items).
- Config via `PROD_*` vars (currently pointed at UIT as a dummy for end-to-end testing until real
  PROD credentials exist). Verified live: browse/filters/regions per env, feedback-only pending
  (PROD 358 vs UIT 17), analyze one PROD conversation → stored PROD-only (UIT untouched).
- ADR-0020 + openapi (`/environments`, `env` params) + tests (store isolation, config).

## Done — execution increment 18 (feedback export + empty-conversation guard)
- Added a **Download** button on the Feedback page (CSV / PDF / JSON) → `GET /api/analysis/feedback/export`.
  Each export includes, per feedback conversation: category, confidence, feedback type + user remark,
  the 3-part root cause (what happened / why / how to avoid), suggestions + recommended action,
  cost & responsiveness metrics, source metadata, and the full de-identified transcript. CSV/JSON via
  stdlib; PDF via `fpdf2==2.8.3`. Contract added to `api/openapi.yaml`.
- Stopped analysing conversations with **no messages** (empty/purged source rows): eligibility +
  queue + on-demand all skip them (was producing hallucinated "resolved" labels); cleaned up the
  308 pre-existing empty-transcript analyses.

## Done — execution increment 17 (feedback tenant/date filters + Markdown tables)
- Added server-backed feedback filters for tenant name, Last 7 days, Last 30 days, and custom
  activity-date ranges; updated the OpenAPI contract and responsive filter layout.
- Extended the safe Markdown renderer with scrollable pipe tables; raw HTML is rendered as safe
  escaped text (React text nodes — never executed, and no longer regex-stripped so content is not
  lost); serialized suggestion arrays now display as formatted bullet lists.
- Verified the reported conversation live: University of Utah, Last 7 days, and Aug 13 custom-date
  filters all return it, and the feedback list/detail routes return 200 after service restarts.
- Green: **client 25 jest + typecheck + lint + production build; server 82 pytest, 3 skipped;
  OpenAPI YAML valid; read-only posture guard passed**.

## Done — execution increment 18 (EU migration completed)
- Diagnosed two EU layouts: a 19-thread platform schema and the authoritative 1,600-conversation
  classic chat schema. Added read-only compatibility for both while keeping US/UK unchanged.
- After classic-schema access was corrected, deleted exactly the 19 approved platform-derived rows
  from the service-owned result store; no source/org data was modified.
- Migrated all **1,600 non-deleted EU conversations** through the normal de-identification + Vertex
  boundary. Final categories: 977 resolved, 544 failed-to-resolve, 16 positive feedback,
  17 negative feedback, and 46 out-of-scope.
- Live verification without restarting the active backend: EU source/overview/API totals all 1,600;
  queue 0, in-flight 0, dead-letter 0, unanalysed 0; read-only posture guard passed.
- SQL result loading now ignores obsolete extra JSON fields such as legacy `enrichment` metadata.

## Next
1. Grow the eval gold set to 100–200 real labelled conversations (≥85% gate).
2. Add server-side search/pagination and trend endpoints once review volume requires them.
3. ~~Scheduler wiring (every 4h)~~ — replaced by a manual analysis trigger (ADR-0019).

## Blockers / needs
- **Credentials:** LangSmith read key; chat DB read-only connection details; Gemini access.
- **Access we lack:** write to any org DB (→ own store); in-VPC hosting.

## Setup checklist status
See `docs/sessions/2026-08-11.md` §"Checklist status" for the per-item CDAO breakdown.
