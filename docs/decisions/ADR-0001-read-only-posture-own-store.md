# ADR-0001 — Read-only posture + service-owned result store

**Status:** Accepted (2026-08-11)

## Context
The org grants **SELECT-only** access to the chat Cloud SQL DB and **no write access to
any org database**. The service runs on Devin Cloud (outside the GCP VPC). We still need
to persist analysis results and serve them to reviewers.

## Decision
- The analysis service is **read-only against all org systems** (SELECT on the chat DB;
  read-only LangSmith).
- Analysis results are written **only** to a **service-owned `ResultStore`**, behind an
  interface. Default backend (hackathon): local **SQLite/JSONL** on the service host.
  Future backend (prod): managed Postgres/GCS behind the same interface.
- No writes to the chat DB, `conversations.meta`, or any org DB — ever.

## Consequences
- Maximally least-privilege; matches what the org allows; no dependency on write grants.
- The reviewer surface reads from our API (backed by our store), not from an org table.
- Not durable/scalable until a managed store is provisioned — acceptable for the
  prototype; pluggable interface makes the swap cheap.

## Alternatives considered
- Write `conversation_analysis` into the chat DB — **rejected** (no write access; wrong
  ownership boundary).
- `conversations.meta` JSONB — **rejected** (still a chat-DB write).
