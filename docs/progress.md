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

## Next
1. **Real ingestion (has creds, needs reachability):** chat-DB (SELECT) reader +
   LangSmith-as-source so the table shows REAL conversations (fixtures are default). The
   chat DB is private-IP — needs a reachable path from where the analyzer runs.
2. Client **detail view** (transcript + per-conversation TTFT/tokens) + override control UI.
3. **Eval harness** (≥85% agreement; resolved-mislabel hard gate).
4. Scheduler wiring (Cloud Scheduler → authenticated `/api/analysis/runs`).

## Blockers / needs
- **Credentials:** LangSmith read key; chat DB read-only connection details; Gemini access.
- **Access we lack:** write to any org DB (→ own store); in-VPC hosting.

## Setup checklist status
See `docs/sessions/2026-08-11.md` §"Checklist status" for the per-item CDAO breakdown.
