# 01 — Vision

## Problem
Today, JAI Assist conversations are only reviewed when a user leaves feedback. Reviewers
therefore see a **biased sliver** of activity and can't act on the silent majority —
including the conversations that quietly failed or fell out of scope.

## Vision
Every completed JAI Assist conversation is **automatically analysed**, **labelled** with a
single category, given a **recommended next step**, and made available to internal
reviewers as a **full, verifiable record** (transcript + feedback + cost + latency) — so
reviewers act on the **whole population**, not just flagged chats.

## Who it's for
Internal reviewers: QA / answer-quality, product, and account/support leads who need to
understand how JAI is performing and where to intervene (see `02-customer.md`).

## Outcomes we want
- 100% of completed conversations carry a category + next step without manual flagging.
- Reviewers can group and count outcomes without reading each conversation.
- Each label is **verifiable** against the underlying transcript, feedback, tokens and
  latency in one place.
- Evidence-based prioritisation: high-frequency failure/out-of-scope patterns surface.

## Non-goals (initial)
- No automated remediation or model retraining ("Reinforced Learning" in the parent Jira
  title refers to a human-feedback triage loop, not RLHF).
- No writes to production systems; the analyser is **read-only** against org data.
- No Jira ticket automation, email, or cross-system root-cause forensics in v1.

## Relationship to Jira J1-93353
This delivers the FR-1..4 slice of the broader "Reinforced Learning on Human Feedback"
feature. Scope overlaps but is not identical; reconciliation is pending PM
(`03-prd.md` §Scope, `progress.md`).

## Guiding priorities
Security → correctness → evidence-based labelling → reliability → maintainability →
observability → cost → speed.
