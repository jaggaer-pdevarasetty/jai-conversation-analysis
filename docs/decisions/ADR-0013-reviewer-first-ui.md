# ADR-0013 — Reviewer-first information architecture

**Status:** Superseded by ADR-0014 (2026-08-11)

## Context
The prototype UI exposes the required data but does not help product managers decide what to
review or what to fix. The overview depends on live tenant/user data while the reviewer contract
is deliberately pooled and de-identified; the list hides loading failures and has little hierarchy;
the detail page separates transcript, evidence, metrics, recommendation, and override into a long
undifferentiated stack. The permanent desktop drawer also makes the application unusable on small
screens.

## Options considered
1. **Visual reskin only.** Smallest change and lowest risk, but preserves the broken hierarchy,
   silent failures, tenant/reviewer mismatch, and weak review workflow.
2. **Reviewer-first redesign on the existing pooled API.** Build a health overview, review queue,
   and evidence-led detail view from the existing list/detail/run responses. This fixes the main
   workflow without expanding the backend contract.
3. **Full analytics platform.** Add server-side search, saved views, trends, exports, and new
   aggregate endpoints. Better for a mature high-volume product, but speculative before reviewer
   usage and retention requirements are known.

## Decision
Choose option 2. The primary navigation is **Health overview → Review queue → Conversation
review**. The overview uses only pooled analysis and run data, surfaces coverage and review
priorities, and links into the queue. The queue makes category, recommendation, confidence,
feedback, telemetry, override state, and analysis time scannable with explicit loading/error/empty
states. The detail view puts the transcript beside a sticky review panel containing the decision,
evidence, telemetry, feedback, audit metadata, and override action.

Tenant/user drill-down is excluded from primary navigation because it conflicts with the pooled,
conversation-ID-only reviewer model in ADR-0007 and AC-10. Existing routes remain untouched until
the separate authorised-admin product and access control are specified.

## Consequences
- No new dependency and no new backend endpoint are required.
- The UI remains usable when the source chat DB is unavailable because its primary pages use the
  service-owned common store.
- The first queue load is capped by the existing API limit; add server-side search/pagination and
  trend endpoints when real volume or reviewer research demonstrates the need.
