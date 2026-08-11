# ADR-0005 — Source of truth is Jira J1-93353; analyse all conversations

**Status:** Accepted (2026-08-11) — confirmed by PM

## Context
There were two candidate specs: the FR-1..4 doc and Jira **J1-93353** ("JAI Assist:
Reinforced Learning on Human Feedback"). They overlap but J1-93353 is broader (richer
categories, severity, root-cause hypothesis, overview/drift report, PII scrub). Population
was ambiguous (all conversations vs feedback-only).

## Decision (per PM)
- **J1-93353 is the source of truth**; it contains the FR-1..4 requirements plus more
  context. FR-1..4 is treated as the core subset.
- **All completed conversations are analysed** (full population, not feedback-only).
- **All data is obtained from LangSmith + the chat DB** (read-only).

## Consequences
- The 5 FR categories are the primary label; J1-93353's richer error taxonomy + extras
  (severity, one-line root-cause, overview/drift) are folded in as secondary/optional
  fields on the roadmap (`docs/08-roadmap.md`).
- Full-population scope confirms the batch analyzer design (not feedback-triggered).
- No dependency on Jira-ticket creation for the core loop.
