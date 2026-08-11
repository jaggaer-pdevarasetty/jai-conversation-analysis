# 07 — Test Strategy

Two runners, matching the stack (ADR-0006): **jest** (client) + **pytest** (server).

## Client (Next.js + jest + Testing-Library)
- **Unit/component:** `client/src/**/*.test.tsx` via jest (`next/jest` transform) +
  `@testing-library/react`. Green in **< 1s**.
- **Semantic selectors only:** `getByRole` / `getByLabelText` — never CSS/XPath.
- **Boundary mocked:** the API layer (`services/analysisApi`) is mocked with `jest.mock`
  (no network); MSW can be added for fetch-level mocking if needed.
- `npm run typecheck` (tsc) and `npm run lint` (next lint) gate the client.

## Server (FastAPI + pytest)
- **Unit:** `server/tests/test_signals.py`, `test_category_analyze.py` — pure domain
  logic (signals, category, analyze). Green in **< 1s**.
- **Integration:** `test_api_integration.py` via FastAPI `TestClient` — list/detail,
  category filter, RFC 7807 error bodies, and an assertion that the OpenAPI doc is 3.1.
- **Boundary mocked:** `test_langsmith_integration.py` mocks the LangSmith HTTP API with
  `httpx.MockTransport` and asserts token/latency parsing.

## Contract (from the OpenAPI spec)
FastAPI emits the OpenAPI 3.1 document (`/openapi.json`); `api/openapi.yaml` is the
human-reviewed contract. CI asserts the served spec is 3.1 on PR; a schema-fuzzing
contract check (schemathesis) is a roadmap add-on.

## CI (`.github/workflows/ci.yml`)
- **client** job: `npm ci` → lint → typecheck → jest (on push + PR).
- **server** job: pytest unit + integration (on push); OpenAPI 3.1 contract check on PR.
- **gitleaks** job: secret scan on full history.

## Reliability rules
- No flaky tests masked by retries — a test that only passes on retry is a bug to fix.
- Tests are deterministic and network-free (boundaries mocked).

## Accuracy / eval (roadmap)
Human gold set (≈30 → 100–200) + confusion matrix to gate LLM categorisation; targets in
`06-nfr-slos.md`.

## Definition of done (per change)
Relevant jest/pytest tests added + green · typecheck/lint clean · acceptance criteria in
`03-prd.md` met.
