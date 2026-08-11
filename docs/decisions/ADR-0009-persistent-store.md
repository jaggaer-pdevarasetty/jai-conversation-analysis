# ADR-0009 — Persistent common store (SQLAlchemy: SQLite default, Postgres via Docker)

**Status:** Accepted (2026-08-11)

## Context
The common store must persist analyses, overrides, and the unanalysed/retry set across
restarts (auditability + reliability NFRs). The team asked for a local Postgres in Docker.
Docker is not available in every dev sandbox, so the default must also work without it.

## Decision
- Introduce `SqlResultStore` (SQLAlchemy) implementing the same interface as the in-memory
  `CommonStore`. Selected via `STORE_BACKEND` (`memory` default for tests; `sql` for
  persistence). URL via `RESULTS_DB_URL`.
- **Default persistent backend = SQLite** (`sqlite:///./data/analysis.db`) — works with no
  Docker. **Postgres** is a drop-in via `docker-compose.postgres.yml` +
  `RESULTS_DB_URL=postgresql+psycopg://…`. Same code path (JSON columns) on both.
- Still **conversation_id-keyed and de-identified** (ADR-0007) — no tenant/user columns.

## Consequences
- Tests keep using the in-memory store (fast, isolated); a dedicated SQLite test proves
  persistence + override + failed-count against a real DB file.
- Production can point at managed Postgres by env alone; no code change.
