# ADR-0004 — Stack: TypeScript / Next.js

**Status:** SUPERSEDED by ADR-0006 (Next.js client + FastAPI server). Kept for history.

## Context
The company project-setup template (`.windsurfrules`) and the readiness checklist are
TypeScript/Node-flavoured (Supertest/MSW, Playwright `getByRole`, `typecheck`,
`*.test.ts`, contract tests from an OpenAPI spec). The reviewer surface also extends a
React/TypeScript dashboard (`jai-agentos-chat/client`). An earlier draft assumed Python
(to reuse the orchestrator's `langchain-google-genai`).

## Decision
Build the analysis service in **TypeScript / Next.js**, with **Postgres accessed
read-only**, on **GCP**, using **LangSmith** (JS SDK) and **Gemini** (JS SDK / LangChain
JS). Rationale: aligns with the company template + the entire test baseline, and with the
React/TS dashboard we extend — one language across API + UI + tests.

## Consequences
- All test-baseline items map to the TS toolchain (Jest, Supertest/MSW, Playwright,
  contract tests from `api/openapi.yaml`).
- We do **not** reuse the Python orchestrator's LLM code; we re-implement the (small)
  Gemini call in TS. Prompts/signals are language-agnostic.
- If the team prefers Python, this ADR is superseded and `07-test-strategy.md` swaps to
  pytest + schemathesis; the architecture is otherwise unchanged.

## Alternatives considered
- **Python** (reuse orchestrator stack) — better LLM-code reuse, but diverges from the
  company template + the TS test baseline + the TS dashboard. Rejected for consistency.
