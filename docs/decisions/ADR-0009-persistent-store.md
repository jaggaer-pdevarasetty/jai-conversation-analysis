# ADR-0009 — Persistent common store on PostgreSQL (container)

**Status:** Accepted (2026-08-11; revised — Postgres only, SQLite dropped)

## Context
The common store must persist analyses, overrides, and the unanalysed/retry set across
restarts (auditability + reliability NFRs). Direction: **store data strictly in a
containerised PostgreSQL** (Docker). Docker isn't installed in this environment, but
**podman** is, so we run the same `postgres:16-alpine` image via podman.

## Decision
- `SqlResultStore` (SQLAlchemy) implements the same interface as the in-memory
  `CommonStore`, backed by **PostgreSQL** (`RESULTS_DB_URL`). Selected via `STORE_BACKEND=sql`.
- **SQLite is not used for storing data** (removed). The in-memory store remains only for
  fast, hermetic unit tests (`STORE_BACKEND=memory`, the default when no DB is configured).
- Local Postgres runs as a container:
  - podman: `podman run -d --name jai-analysis-postgres -e POSTGRES_USER=jai
    -e POSTGRES_PASSWORD=jai -e POSTGRES_DB=analysis -p 5433:5432 postgres:16-alpine`
  - Docker: `docker compose -f docker-compose.postgres.yml up -d`
- Still **conversation_id-keyed and de-identified** (ADR-0007) — no tenant/user columns.

## Consequences
- `test_store_sql.py` runs against Postgres (`TEST_DATABASE_URL`, default the local
  container) and **skips** cleanly when no Postgres is reachable (e.g. CI without a
  Postgres service) — so it never silently uses SQLite.
- Production points `RESULTS_DB_URL` at managed Cloud SQL Postgres by env alone.
- Verified end-to-end: 6 analysed conversations persisted to the container Postgres.
