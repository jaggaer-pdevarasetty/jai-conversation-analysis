# JAI Conversation Analysis

Automatically analyse **every completed JAI Assist conversation**, label it with one of
five categories, attach a **recommended next step**, and expose a **full reviewer record**
(transcript + feedback + tokens + latency) to internal reviewers.

Source of truth: Jira **J1-93353** (FR-1..4 is the core subset). Read
`docs/05-architecture.md` first. Decisions: `docs/decisions/`.

## Posture (hard constraints)
Read-only against org systems: **SELECT-only** on the chat DB, **read** LangSmith. We
write **only** to our own store. (ADR-0001.)

## Layout (mirrors jai-agentos-chat)
```
client/   Next.js + React 18 + MUI + jest      — reviewer UI
server/   FastAPI (Python 3.13) + pytest        — analysis + read API
api/      openapi.yaml (OpenAPI 3.1 contract)
docs/     product + technical docs, ADRs, session logs
.github/  CI (client jest + server pytest + gitleaks), dependabot
```

## Quickstart
```bash
# server (FastAPI)
cd server && python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                 # 20 tests, < 1s
uvicorn app.main:app --port 8000 # http://localhost:8000/docs

# client (Next.js)
cd client && npm ci
npm test                         # jest, < 1s
npm run dev                      # http://localhost:3000  (set NEXT_PUBLIC_API_BASE)
```

## Status
Prototype scaffold on **mock fixtures**, tests green both sides. Wiring the real chat DB
(SELECT), LangSmith, and Gemini is gated on credentials — see `docs/progress.md`.
