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
scheduled cadence (every 4h, eligible after 5-min inactivity), **de-identification +
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

## Next
1. Repopulate `analysis` from `chatdb` via Vertex + restart backend (approved) → UI shows real data.
2. Fix `.env`: `CHAT_DB_URL` db = `jai_agentos_uit`, `CHAT_DB_SCHEMA=jai_agentos_schema_uit`, `SOURCE=chatdb`.
3. Grow the eval gold set to 100–200 real labelled conversations (≥85% gate).
4. Client detail view (transcript + tokens) + override UI.
5. Scheduler wiring (every 4h) with rate-limit-aware batch.

## Blockers / needs
- **Credentials:** LangSmith read key; chat DB read-only connection details; Gemini access.
- **Access we lack:** write to any org DB (→ own store); in-VPC hosting.

## Setup checklist status
See `docs/sessions/2026-08-11.md` §"Checklist status" for the per-item CDAO breakdown.
