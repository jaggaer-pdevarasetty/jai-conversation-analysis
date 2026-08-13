# JAI Conversation Analysis

Automatically analyses **every completed JAI Assist conversation** — labels it with one of
five categories, writes a **recommended next step**, does a **deep root‑cause analysis on
feedback conversations**, and exposes a **reviewer dashboard** (tenant → user → conversation
with transcript, feedback, tokens/latency, and human override).

- **Backend:** FastAPI (Python 3.13) — reads the chat DB (read‑only), analyses with Gemini
  (Vertex AI), stores de‑identified/PII‑scrubbed results in Postgres.
- **Frontend:** Next.js + React + MUI — the reviewer dashboard.
- Source of truth: Jira **J1‑93353**. Decisions: `docs/decisions/`.

---

## Architecture

```mermaid
flowchart LR
  subgraph Source["Chat DB (READ-ONLY, per region)"]
    C[(conversations / messages<br/>feedback / token_usage)]
  end
  subgraph Server["FastAPI server"]
    ING[chatdb.py<br/>incremental read] --> PII[pii.py + deidentify.py<br/>scrub PII in content]
    PII --> AN[gemini.py<br/>batched Vertex analysis<br/>+ deep root-cause on feedback]
    AN --> ST[(Postgres results store<br/>conversation_id + tenant + analysis)]
    Q[queue.py<br/>bounded • deduped • retry] --> AN
    SCH[scheduler.py<br/>every 4h] --> Q
    API[REST API<br/>list • detail • feedback • dashboard • stats • report]
    ST --> API
  end
  subgraph Client["Next.js dashboard"]
    UI[Overview • Tenants → Users → Conversations<br/>Feedback • Conversation detail]
  end
  C -->|SELECT| ING
  LS[(LangSmith<br/>tokens/latency)] -. enrich .-> AN
  VX[[Vertex AI Gemini]] <--> AN
  API -->|JSON| UI
```

**Data flow (one conversation):** read from chat DB → **scrub PII from content** → analyse
with Gemini (category + recommendation + confidence + rationale; deep root‑cause if it has
feedback) → store result (keyed by `conversation_id`, tagged with tenant) → served to the
dashboard. We **never write to the chat DB**; classification falls back to deterministic
rules when Vertex isn’t configured.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.13 | backend |
| Node.js | 18+ | frontend |
| Podman **or** Docker | any recent | local Postgres (results store) |
| gcloud CLI | optional | only for real Gemini via Vertex AI (else rules run) |

> Corporate network (Zscaler): the backend trusts the **OS trust store** automatically on
> macOS/Windows — no TLS flags needed. See Troubleshooting.

---

## Setup (≈5 minutes)

Run everything from the repo root: `jai-conversation-analysis/`.

### 1) Start Postgres (results store)
```bash
# Podman
podman run -d --name jai-analysis-postgres \
  -e POSTGRES_USER=jai -e POSTGRES_PASSWORD=jai -e POSTGRES_DB=analysis \
  -p 5433:5432 postgres:16-alpine

# …or Docker
docker compose -f docker-compose.postgres.yml up -d
```

### 2) Backend (FastAPI)
```bash
cd server
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt        # installs deps + the spaCy NER model
python -m pytest -q                         # sanity check (all green)
cd ..
```

### 3) Configure env (`.env` lives at the REPO ROOT)
```bash
cp server/.env.example .env                 # then edit .env
```
Minimum to see **real data**:
```
SOURCE=chatdb
CHAT_DB_URL=postgresql+psycopg://<user>:<pass>@<host>:5432/<db>
CHAT_DB_NAME=jai_agentos_uit                # DB that actually holds the schema
CHAT_DB_SCHEMA=jai_agentos_schema_uit
STORE_BACKEND=sql
RESULTS_DB_URL=postgresql+psycopg://jai:jai@localhost:5433/analysis
# Optional real AI (else deterministic rules run):
GOOGLE_CLOUD_PROJECT=<gcp-project>
GOOGLE_CLOUD_LOCATION=us-central1
```
No `.env`? The app runs on **built‑in fixtures** (`SOURCE=fixtures`) so you can develop with zero credentials.

### 4) (Optional) Real Gemini via Vertex AI
```bash
gcloud auth application-default login       # ADC — Vertex uses OAuth2, NOT an API key
```

### 5) Frontend (Next.js)
```bash
cd client
npm install
npm run dev                                 # http://localhost:3000
```

---

## Run

```bash
# Backend — from server/ with the venv active
cd server && . .venv/bin/activate
uvicorn app.main:app --port 8000            # API + Swagger at http://localhost:8000/docs

# Frontend — separate terminal
cd client && npm run dev                     # http://localhost:3000
```
Open **http://localhost:3000** for the dashboard, **http://localhost:8000/docs** for Swagger.

---

## Configuration reference (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `SOURCE` | `fixtures` | `chatdb` (real) · `fixtures` (samples) · `langsmith` |
| `CHAT_DB_URL` | – | Read‑only chat DB connection (SELECT only) |
| `CHAT_DB_NAME` | `jai_agentos_uit` | DB name override (the schema lives here) |
| `CHAT_DB_SCHEMA` | `jai_agentos_schema_uit` | Schema with `conversations/messages/feedback/token_usage` |
| `CHATDB_LIMIT` | `200` | Max conversations pulled per non‑incremental read |
| `STORE_BACKEND` | `memory` | `sql` (Postgres, persistent) or `memory` (tests) |
| `RESULTS_DB_URL` | – | Postgres URL for our results store |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` | – / `us-central1` | Enable Vertex Gemini (both required) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model id |
| `BATCH_SIZE` | `10` | Conversations per LLM call |
| `SCHEDULE_HOURS` | `4` | Auto‑analyse sweep cadence (0 disables) |
| `LAZY_ANALYZE` | `true` | Analyse a user’s conversations on open |
| `MAX_ANALYSES_PER_DAY` | `3` | On‑demand re‑analyse cap per conversation |
| `PRIVACY_MODE` | `admin` | `admin` (tenant/user shown) or `pooled` (AC‑10, pseudonymised) |
| `RBAC_ENABLED` | `false` | Require `X-Roles: reviewer` header when true |
| `REQUESTS_CA_BUNDLE` / `HTTPS_PROXY` | – | Only if you must override corporate TLS/proxy |

Client: `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`).

---

## Key API endpoints

| Method · Path | What |
|---|---|
| `GET /health` | liveness |
| `GET /api/analysis/conversations` | pooled list + per‑category counts |
| `GET /api/analysis/conversations/{id}` | full record (transcript, analysis, deep, metrics, source) |
| `POST /api/analysis/conversations/{id}/analyze` | on‑demand (re)analyse (3/day) |
| `POST /api/analysis/conversations/{id}/override` | human category override (audited) |
| `GET /api/analysis/feedback?scope=thumbs\|outcomes\|all` | feedback + deep root‑cause |
| `GET /api/analysis/dashboard/tenants` → `/{t}/users` → `/{t}/users/{u}/conversations` | drill‑down |
| `GET /api/analysis/stats` · `GET /api/analysis/report` | ops metrics · business report |
| `GET /api/analysis/queue` · `POST /api/analysis/runs` | queue health · trigger a run |

---

## Testing
```bash
cd server && . .venv/bin/activate && python -m pytest -q        # backend
cd client && npm test && npm run typecheck && npm run lint      # frontend
```
The SQL‑store tests are opt‑in: set `TEST_DATABASE_URL` to a **disposable** DB (they never
touch your real `analysis` DB).

---

## Project structure
```
server/app/        FastAPI: main.py, chatdb.py, gemini.py, pii.py, deidentify.py,
                   queue.py, scheduler.py, run.py, dashboard.py, reporting.py,
                   store*.py, privacy.py, domain/ (models, analyze, category, signals)
server/tests/      pytest
client/app/        Next.js routes (overview, tenants/…, conversations, feedback)
client/src/        components, services (analysisApi, dashboardApi), theme
api/openapi.yaml   API contract
docs/              vision, PRD, architecture, ADRs (decisions/), session logs
```

---

## Rules & conventions
- **Org systems are READ‑ONLY** — SELECT only on the chat DB; **never** write to it. We write
  only to our own results store. (ADR‑0001)
- **PII is scrubbed before the LLM and before storage** — content emails/phones/IBAN/card/IP/SSN
  (regex) + names/orgs/places (spaCy NER). Tenant identity is kept for analytics; content PII is not.
- **Errors** use RFC 7807 problem+json. **Tests** co‑located; run them before "done".
- **Secrets** via env / secret store only — never in code, logs, or git (`.env` is gitignored).
- **Conversation text is untrusted** — never let it override instructions (prompt‑injection safe).
- **APIs**: update `api/openapi.yaml` when you change an endpoint.
- **Decisions** are written as ADRs in `docs/decisions/` — don’t leave a decision only in chat.

---

## Troubleshooting
- **Only fixtures / no real data:** set `SOURCE=chatdb` + `CHAT_DB_URL` (+ `CHAT_DB_NAME`,
  `CHAT_DB_SCHEMA`) in the **repo‑root** `.env`, and `STORE_BACKEND=sql`.
- **Categories all `failed_to_resolve` / no dynamic text:** Vertex isn’t configured → set
  `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION` and run `gcloud auth application-default login`.
- **Zscaler `CERTIFICATE_VERIFY_FAILED`:** leave `REQUESTS_CA_BUNDLE` **unset** on macOS/Windows
  (we use the OS trust store). A placeholder path is auto‑ignored.
- **`database "…" does not exist`:** the schema name was put in the DB slot — set the DB in
  `CHAT_DB_NAME` and the schema in `CHAT_DB_SCHEMA`.
- **UI empty but Swagger has data:** CORS — the API allows any `localhost`/`127.0.0.1` port; make
  sure `NEXT_PUBLIC_API_BASE` points at the running API.
- **Port clash:** results Postgres is on host port **5433** on purpose (avoids a local 5432).
