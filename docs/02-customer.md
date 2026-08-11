# 02 — Customer & Personas

The "customers" of this system are **internal reviewers**, not end users.

## Primary persona — Answer-Quality / QA Reviewer
- **Goal:** understand how JAI is performing across all conversations; find failures and
  out-of-scope requests to fix.
- **Today's pain:** only sees conversations that received a thumbs rating; no way to act
  on the silent majority; must open conversations one by one to judge outcome.
- **Needs:** a categorised, countable list of conversations; a suggested next step;
  ability to open the full record to verify a label and judge cost/responsiveness.

## Secondary persona — Product / Roadmap Owner
- **Goal:** spot high-frequency issues and popular out-of-scope requests to prioritise.
- **Needs:** aggregate counts by category; drill-down into representative examples.

## Secondary persona — Account / Support Lead
- **Goal:** catch dissatisfaction and abandonment early for specific tenants.
- **Needs:** filter by category, tenant, and date; see feedback text alongside the label.

## Access & trust
- Reviewers are authenticated internal admins (gated by `jai_administrative_permission`
  in the existing dashboard).
- Reviewers must be able to **verify** every label against source evidence (transcript,
  feedback, tokens, latency) — trust requires transparency.

## Privacy expectations
Conversations may contain customer PII. Reviewers see transcripts under admin gating;
PII is scrubbed before any text is sent to the LLM (`06-nfr-slos.md`, `05-architecture.md`).

## Jobs-to-be-done
1. "Show me all conversations and what happened, not just the ones with feedback."
2. "Tell me what to do about each one without me diagnosing it."
3. "Let me verify the label and see cost/latency in the same place."
4. "Let me count and group outcomes to find patterns."
