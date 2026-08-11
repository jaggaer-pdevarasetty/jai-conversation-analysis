# 05 — Architecture

> Read before implementing. Decisions in `docs/decisions/`. Source of truth: **J1-93353**
> (ADR-0005). Stack: **Next.js client + FastAPI server** (ADR-0006).

## Where the chats live (source of record)
Per Confluence **"Interim JAI Agentic Platform – 26.1 Architecture"** (JDDEV/927268867),
JAI Assist conversations are stored in **GCP Cloud SQL for PostgreSQL** — "Chat history,
Conversation context, Agent checkpoints and execution state". It is **private-IP only**,
reachable **only from inside the VPC** (Private Service Access); creds in Secret Manager.
RAG docs live in Datastore (separate); LangSmith is the separate observability/eval plane.

**Two distinct databases — do not conflate:**
- **Chat DB (source, READ-ONLY):** the private-IP Cloud SQL Postgres above. We only SELECT.
- **Common store (ours):** a *separate* DB (local Postgres/SQLite, ADR-0009) holding only
  our **de-identified analysis results**. Never the chat DB.

## Access constraints (ADR-0001)
| Resource | Access | Consequence |
|---|---|---|
| Chat DB (Cloud SQL Postgres, private-IP) | **SELECT only** | read conversations/messages/feedback/token_usage; no writes anywhere in it; reachable only in-VPC / via Cloud SQL Auth Proxy |
| Any org DB | **no write** | analysis results live only in our own common store |
| LangSmith | read (15-day retention) | authoritative prompt/input/output tokens + timing |
| LLM | Gemini | category + next-step generation |

## Two-package repo (mirrors jai-agentos-chat)
```
client/   Next.js + React 18 + MUI + jest        → reviewer UI (FR-2/3/4 surface)
server/   FastAPI (Python 3.13) + pytest         → analysis + read API
api/      openapi.yaml (OpenAPI 3.1 contract; FastAPI also serves /openapi.json)
docs/     product + technical docs, ADRs, sessions
```

## Runtime shape (scheduled batch, de-identified common area)
```
 Scheduler (every 4h)                     server/ (FastAPI)                        client/ (Next.js)
   ─ trigger run ─────────────►  INGEST  read chat DB (SELECT) + LangSmith           fetch() → read API
                                   │      (tenant-scoped; eligible = inactive ≥5m)     → MUI table + filter
                                   ▼                                                   → open record
                                DE-IDENTIFY  strip PII + tenant/user identifiers       → human override
                                   │         (nothing identifying leaves this step)
                                   ▼
                                ANALYZE  deterministic signals + Gemini → category(1of5) + next step
                                   │      (non-English still categorised; retry queue on failure)
                                   ▼
                                COMMON STORE  key = conversation_id ONLY (no tenant/user);
                                   │          category, next step, override audit, metrics, run/status
                                   ▼
                                READ API  GET /api/analysis/conversations[/{id}]  (RFC 7807; reviewer RBAC)
                                          POST override (audited)   ·   unanalysed count exposed
```
**Boundaries (NFR):** ingest runs with tenant-scoped read access; **de-identification is a
hard boundary** — only conversation-ID-keyed, PII/tenant-free content passes into the
COMMON STORE. The store and read API can reference a conversation by **ID only**; the ID
does not resolve to tenant/user from within the common area (attribution NFR, AC-10).
Read-only against the org; writes only to the service-owned common store.

## Eligibility & scheduling (NFR)
Runs every 4 hours; a conversation is eligible once **inactive ≥ 5 min** and not already
analysed. Failed analyses are queued for the next run; the **unanalysed count is exposed**
via the API and shown in the UI (AC-9). See ADR-0008.

## De-identification & attribution (NFR)
De-identify before the common store: scrub PII from message content and **drop tenant_id /
user_id** — the common record carries `conversation_id` + de-identified content + analysis
+ metrics only. Any ID→tenant lookup (if needed operationally) lives outside the common
area. See ADR-0007.

## Human override (auditability NFR)
Reviewers may override the assigned category; the override is stored as an auditable event
(who / when / old → new) against the conversation ID, alongside the model's original label.

## Server modules (`server/app/`)
- `domain/models.py` — dataclasses: Message, Feedback, Conversation, Signals, AnalysisRecord, CATEGORIES.
- `domain/signals.py` — deterministic: normalize/similarity, repeated-prompt, abandonment, error, feedback, PII scrub, fluff strip.
- `domain/category.py` — `derive_category` (fallback + LLM prior) + `recommended_next_step`.
- `domain/analyze.py` — `analyze(conversation)` → AnalysisRecord.
- `store.py` — InMemoryResultStore (the only thing we write). `fixtures.py` — sample data.
- `langsmith.py` — read client (tokens/latency). `problem.py` — RFC 7807. `main.py` — FastAPI app + routes.

## Client modules (`client/`)
- `app/page.tsx` — operational Overview combining aggregate tenant coverage, analysis outcomes, telemetry, run status, and recent records.
- `app/tenants/` — authorised tenant → users → conversations administration workflow.
- `app/conversations/` — separate pooled review queue and de-identified conversation-review routes.
- `src/services/dashboardApi.ts` — typed tenant/user/conversation dashboard fetch layer.
- `src/services/analysisApi.ts` — typed pooled list/detail/run fetch layer.
- `src/components/ReviewerTable.tsx` — server-paginated, searchable, filterable pooled review queue.
- `src/components/AnalysisQueuePanel.tsx` — polling view of real queued/in-flight conversation IDs.
- `src/components/ConversationDetail.tsx` — transcript + evidence + metrics + feedback + override audit.
- `src/components/MarkdownContent.tsx` — safe React renderer for the Markdown subset used in untrusted chat content.
- `src/components/AppShell.tsx` / `src/theme.ts` — responsive navigation, privacy-scope labels, shared MUI design system.
- `src/config.ts` — API base URL.

## Correlation identifiers (verified in the org repos)
`conversation_id == thread_id`; `message_id → LangSmith run_id via uuid5`. LangSmith run
metadata carries conversation_id / thread_id / message_id / tenant_id / hashed user_id /
intent / frustrated / has_error. TTFT + prompt tokens come from LangSmith (ADR-0003).

## Security posture
Read-only against org; writes only to own store; PII scrubbed before the LLM; conversation
text treated as untrusted (prompt-injection safe); admin-gated API; secrets via env only.
See `06-nfr-slos.md`.
