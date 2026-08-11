# ADR-0016 — Server pagination and live analysis queue visibility

**Status:** Accepted (2026-08-11)

## Context
The pooled review queue loaded up to 200 records and filtered only that client-side subset, so page
counts and filters were misleading as analysis coverage grew. The production analysis queue exposed
aggregate depth but not the real conversation IDs or their queued/in-flight state. Tenant and user
conversation lists also became too long for one screen.

## Options considered
1. **Client-side pagination only.** Smallest UI change, but still downloads the full data set and
   produces incorrect filters beyond the loaded subset.
2. **Server-backed review pagination plus live queue items.** Correct totals, bounded responses,
   filter/sort consistency, and truthful queue visibility using the existing service.
3. **Add an external queue and search service now.** Durable and horizontally scalable, but beyond
   the current single-instance deployment requirement.

## Decision
Choose option 2. The pooled conversations API owns search, category/confidence/review-state filters,
sorting, limit, offset, and filtered totals. The queue API returns paginated real conversation IDs
with queued, analysing, or retrying status, attempt, and enqueue time. The UI polls it every three
seconds without triggering analysis. User conversations use SQL limit/offset; the tenant directory
uses bounded client-side pages because its source endpoint is already a small aggregate response.

## Consequences
- Review pagination and counts stay correct beyond 200 records.
- The UI displays real in-process queue work and an explicit idle/inactive state; it never invents
  progress.
- Queue items are still lost on process restart because the current queue is in-process. Replace the
  queue implementation with Cloud Tasks/PubSub/Redis when multi-instance durability is required.
