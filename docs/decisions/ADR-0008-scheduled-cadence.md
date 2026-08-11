# ADR-0008 — Scheduled batch cadence + eligibility + retry

**Status:** Accepted (2026-08-11) — from J1-93353 §7 (cadence, reliability) + AC-9, AC-11

## Context
The ticket specifies analysis runs **on a schedule, not per conversation**: a conversation
is eligible once **inactive for ≥ 5 minutes**, and runs execute **every 4 hours**. Failed
analyses must be retried and the **unanalysed count kept visible**.

## Decision
- **Batch analyzer** triggered every 4 hours. In production the trigger is external
  (Cloud Scheduler → an authenticated endpoint, or a scheduled job), so the API stays
  stateless and horizontally scalable; locally it can be invoked on demand / by a timer.
- **Eligibility:** `last_activity < now - 5min` AND not already analysed (idempotent on
  conversation_id). Conversations active within the last 5 min are deferred to the next run
  (AC-11).
- **Retry + visibility:** conversations whose analysis fails (e.g. model unavailable) are
  recorded with a `failed`/`pending` status and retried next run; the read API exposes an
  **unanalysed / failed count** the UI surfaces (AC-9). Failures are never silently dropped.
- Each run has a run record (started/completed, counts: analysed / failed / skipped).

## Consequences
- Adds a run/eligibility layer over the analyzer + a status field on records.
- The current fixture-seeded scaffold must gain: eligibility selection, run tracking, and a
  retry/status model (change vs current scaffold).
- Trigger mechanism (Cloud Scheduler vs in-process timer) is an infra choice confirmed at
  deployment; the analyzer entrypoint is the same either way.
