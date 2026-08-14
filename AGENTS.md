# AGENTS.md — JAI Conversation Analysis

Operating guide for AI agents and humans in this repo. Keep it **current**: if a command,
path, or decision changes, update it in the same change.

## What this is
Automatically analyse **every completed JAI Assist conversation** and label it (5
categories) with a **recommended next step** and a **full reviewer record** (transcript,
feedback, tokens, latency). Source of truth: Jira **J1-93353** (FR-1..4 is the subset).
All data comes from **LangSmith + the chat DB** (read-only). Requirements: `docs/03-prd.md`.

## Repo layout (two packages, mirrors jai-agentos-chat)
- `client/` — **Next.js + React 18 + MUI + jest** reviewer UI.
- `server/` — **FastAPI (Python 3.13) + pytest** read API (analysis + serving).
- `api/openapi.yaml` — OpenAPI 3.1 contract (FastAPI also serves `/openapi.json`).
- `docs/` — product + technical docs, ADRs (`docs/decisions/`), session logs (`docs/sessions/`).

## Stack & conventions (ADR-0006)
- Frontend mirrors the chat client: React 18.3, MUI 6, TypeScript, services layer,
  Testing-Library (`getByRole`/`getByLabel`, not CSS). Test runner: **jest**.
- Backend: **FastAPI + pytest**, dataclass domain model, RFC 7807 errors.
- Config/secrets via env or secret store — never hard-coded.

## Access posture (hard constraints — ADR-0001)
- Chat DB: **SELECT only**. **No write to any org DB.**
- LangSmith: **read** (15-day retention) — authoritative for tokens + latency.
- Results persist **only** to our own store.

## Commands
```
# client (Next.js)
cd client && npm ci && npm test        # jest (< 1s)
npm run typecheck && npm run lint
npm run dev                            # http://localhost:3000
# Stop `next dev` before `npm run build`; both use .next and cannot run safely together.

# server (FastAPI)
cd server && python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                       # unit + integration (< 1s)
uvicorn app.main:app --reload --port 8000
```

## The Loop (every task)
EXPLORE → PLAN (3 options + trade-offs → `docs/decisions/`) → EXECUTE (one module) →
VERIFY (tests + acceptance) → COMPACT (`docs/progress.md` + `docs/sessions/<date>.md`).

## Session discipline
Start by pasting current state from `docs/05-architecture.md` + `docs/progress.md`, name one
task, confirm. End by updating `docs/progress.md`, writing a `docs/sessions/<date>.md` log,
committing with an explainable message, and never leaving a decision only in chat — write an ADR.

## Golden rules
Repo is memory · one task per session · every change ships with a test · cross-model review
each PR (Opus: architecture/security, Sonnet: implementation) · never commit code you can't explain.

## Model routing
Opus → architecture + security review. Sonnet → implementation.

## Definition of done
Tests green (jest + pytest) · acceptance criteria (`docs/03-prd.md`) met · docs + progress
updated · ADR written if a decision was made.
