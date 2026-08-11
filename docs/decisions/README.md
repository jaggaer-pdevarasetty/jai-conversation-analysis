# Architecture Decision Records (ADRs)

Decisions live here as ADRs — **never only in a chat thread**. One decision per file.

## Format
`ADR-NNNN-short-title.md` with: Status (Proposed / Accepted / Superseded), Context,
Decision, Consequences, and (optionally) Alternatives considered.

## Index
- ADR-0001 — Read-only posture + service-owned result store
- ADR-0002 — LLM decides the category (signals as hints)
- ADR-0003 — Source token & latency metrics from LangSmith
- ADR-0004 — Stack: TypeScript / Next.js — **superseded by ADR-0006**
- ADR-0005 — Source of truth is Jira J1-93353; analyse all conversations
- ADR-0006 — Stack: Next.js client + FastAPI server (mirrors jai-agentos-chat)
- ADR-0007 — De-identification boundary + conversation-ID-only attribution
- ADR-0008 — Scheduled batch cadence + eligibility + retry
- ADR-0009 — Persistent common store on PostgreSQL (container; SQLite dropped)
- ADR-0010 — Gemini classification via Vertex AI (enterprise) + rules fallback
- ADR-0011 — Evaluation harness + accuracy hard gate (≥85%, resolved-mislabel critical)
- ADR-0012 — Conversation sources (fixtures | LangSmith); Zscaler via env CA
- ADR-0013 — Reviewer-first information architecture on the pooled API — **superseded by ADR-0014**
- ADR-0014 — Operational overview with tenant administration and pooled review workflows
- ADR-0015 — Safe transcript Markdown and responsive review filters

## Rule
When you make a non-trivial choice during a task, add or update an ADR in the same change,
and link it from `progress.md`.
