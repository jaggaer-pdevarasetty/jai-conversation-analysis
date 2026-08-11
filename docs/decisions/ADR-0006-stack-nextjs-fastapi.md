# ADR-0006 — Stack: Next.js client + FastAPI server (mirrors jai-agentos-chat)

**Status:** Accepted (2026-08-11) — supersedes ADR-0004

## Context
The repo is a **frontend** deliverable that also needs its own server. Direction from the
team: use **Next.js** for the frontend, keep tooling aligned with the existing repos, and
**don't introduce unfamiliar frameworks**. Analysis of `jai-agentos-chat` shows a
`client/` (React 18 + MUI + jest) + `server/` (Python FastAPI) split.

## Decision
Two packages in one repo, mirroring the chat repo:
- **`client/`** — **Next.js + React 18.3 + MUI 6 + TypeScript**, tests with **jest** +
  Testing-Library (semantic selectors). Matches the chat client's conventions.
- **`server/`** — **FastAPI (Python 3.13) + pytest**, the read API. FastAPI emits the
  OpenAPI 3.1 contract natively.

## Consequences
- Cheat-sheet "Vitest or **Pytest**" is met by the FastAPI side; the client uses jest
  (the chat client's runner) rather than Vitest — a deliberate deviation to match the org
  convention (noted; if the assessor requires Vitest specifically, revisit).
- Supersedes ADR-0004 (TypeScript/Next.js single-package with Fastify/Vitest). The
  earlier Fastify/Vitest/Playwright scaffold was removed.
- Client↔server contract is the OpenAPI spec; the client mocks the API boundary in tests.

## Alternatives considered
- Single Next.js app with route handlers (no separate FastAPI) — rejected: the org
  convention is a Python FastAPI server (as in jai-agentos-chat).
- Webpack Module Federation (exact chat client framework) — the team chose Next.js instead.
