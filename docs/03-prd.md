# 03 — Product Requirements (PRD)

Mirrors Jira **J1-93353** (source of truth, ADR-0005). Keep in sync with the ticket.

## Problem & target user
- Only thumbs-down conversations are reviewed today → most interactions are never examined;
  no-feedback failures (abandonment, repeated prompts, mid-conversation exit) are invisible;
  manual review doesn't scale; cost/responsiveness isn't visible next to the conversation.
- **Users:** JAI product managers & reviewers (decide what to fix next); prompt owners
  (act on specific recommendations).

## Functional requirements
- **FR-1** — On completion, a conversation is analysed **automatically, without flagging**,
  so reviewers act on the full population (not just feedback conversations).
- **FR-2** — An analysed conversation carries exactly one category from the defined set:

  | Category | Applies when |
  |---|---|
  | JAI resolved user query | request answered and the conversation closed out |
  | JAI failed to resolve | repeated/rage prompts, dissatisfaction, abandonment, mid-conversation exit |
  | Positive feedback | explicit positive feedback |
  | Negative feedback | explicit negative feedback |
  | Out of scope | JAI does not currently perform the requested action |

- **FR-3** — A recommended next step is shown for each analysed conversation.
- **FR-4** — The full record is viewable: conversation (by **conversation ID**, openable);
  messages in order; feedback (thumbs + free text); analysis (category + next step);
  latency — time to first token **[TBD: per message / per conversation / both]**;
  tokens — input / output / prompt counts.

## Non-functional requirements (see `06-nfr-slos.md` for detail)
- **Cadence:** scheduled, not per-conversation. Eligible after **5 min inactivity**;
  runs **every 4 hours**.
- **AI accuracy:** **≥85%** category agreement with a human; labelling a failed/out-of-scope
  conversation as *resolved* is a **critical failure**; adjacent-category confusion tolerable.
- **RBAC:** restricted to JAI product & internal reviewers; **pooled, not per-tenant**.
- **De-identification:** no PII, no tenant-identifying info in the common area; de-identify
  **before** content enters it (the control that permits pooling).
- **Attribution:** a conversation and its analysis are attributable to the **conversation
  ID and nothing further**; the ID must not resolve to tenant/user from within the common area.
- **Auditability:** category, next step, and any **human override** retained as an
  auditable record against the conversation ID.
- **Reliability:** failed analyses are queued and retried next run; **unanalysed counts
  remain visible** (never silently excluded).
- **Telemetry completeness:** latency + tokens captured at generation time; **missing
  telemetry shown as missing, not zero**.

## Acceptance criteria (from the ticket)
- **AC-1 (FR-1):** after a scheduled run, every eligible conversation is analysed, incl.
  those with no feedback.
- **AC-2 (FR-2):** an analysed conversation carries exactly one category.
- **AC-3 (FR-2):** repeated prompt then left without resolution → *failed to resolve*.
- **AC-4 (FR-2):** requesting an action JAI doesn't perform → *out of scope* (not failure).
- **AC-5 (FR-3):** a recommended next step is present alongside the category.
- **AC-6 (FR-4):** record shows conversation ID, ordered messages, feedback, category,
  next step, TTFT, and input/output/prompt token counts.
- **AC-7 (FR-4, edge):** missing latency/token telemetry shown as **unavailable**, not zero.
- **AC-8 (FR-1/2, edge):** non-English conversation still receives a category.
- **AC-9 (FR-1, failure):** model unavailable mid-run → unanalysed queued for retry, count visible.
- **AC-10 (NFR):** any tenant's conversation appears by conversation ID only; no PII/tenant
  info in content; ID doesn't resolve to tenant/user from within the common area.
- **AC-11 (NFR cadence):** conversation last active < 5 min before a run → excluded this
  run, picked up next run.

## Scope
- **In:** scheduled full-population analysis; category + next step + full record; pooled,
  de-identified common area; reviewer read API + UI; human override; retry + visible
  unanalysed count.
- **Out (v1):** remediation, model retraining, Jira/email automation, cross-system RCA.
- **Open:** TTFT granularity (FR-4); confirm ≥85% accuracy threshold.
