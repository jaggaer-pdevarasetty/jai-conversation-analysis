# ADR-0019 — Manual analysis trigger (no scheduled cadence)

**Status:** Accepted (2026-08-18)

## Context
Analysis previously ran automatically: a full sweep at boot plus a periodic sweep every
`SCHEDULE_HOURS` (default 4h) via `Scheduler`, enqueuing eligible, not-yet-analysed
conversations (ADR-0008). For the reviewer workflow this was undesirable: reviewers wanted to
decide *when* the (LLM-costed) analysis runs, to see how many new conversations are pending
before committing, and to avoid a fixed cadence that runs work nobody is watching.

## Decision
Replace the schedule with an explicit, two-step **manual trigger**, exposed in the UI (app bar
+ review queue) and driven by two endpoints:

- `GET /api/analysis/analyze/pending?region=` — **fetch, don't analyse**: returns the count of
  eligible not-yet-analysed conversations for the selected region (or all), a per-region
  breakdown, and brief details for a sample (computed with a single `analysed_ids()` query).
- `POST /api/analysis/analyze/sweep?region=` — **start**: enqueues those conversations into the
  existing `AnalysisQueue` in the background (deduped; returns `already_running` if a sweep is in
  flight). Progress is visible via `GET /api/analysis/queue`.

No boot sweep and no periodic `Scheduler` are wired up. Eligibility (idle ≥ 5 min, not deleted)
and the queue's dedup/retry/dead-letter behaviour are unchanged. `SCHEDULE_HOURS` and
`scheduler.py` remain in the tree, unused, so a scheduled cadence can be re-enabled later
without new code.

## Consequences
- Reviewers control cost/timing; nothing is analysed until someone clicks. New conversations
  are only picked up on a manual trigger (documented in the UI).
- Analysis counts **conversations, not messages**, and honours the 5-minute idle rule.
- Single-instance assumption is now irrelevant for scheduling (there is no background cadence).
- Supersedes the periodic-cadence part of **ADR-0008**; the eligibility + queue design there
  still applies.

## Alternatives considered
- **Keep the 4h schedule** — rejected: runs unwatched LLM work and gives reviewers no control.
- **Configurable cadence (SCHEDULE_HOURS=0 to disable)** — kept as a latent capability, but the
  default posture is manual per this ADR.
- **Fully synchronous "analyse now"** — rejected: analysing thousands of conversations must not
  block a request; the background queue + queue-status polling is used instead.
