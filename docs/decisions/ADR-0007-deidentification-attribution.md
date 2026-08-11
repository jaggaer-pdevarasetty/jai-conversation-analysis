# ADR-0007 — De-identification boundary + conversation-ID-only attribution

**Status:** Accepted (2026-08-11) — from J1-93353 §7 (de-identification, attribution) + AC-10

## Context
The common analysis area pools conversations across tenants and is visible to reviewers.
The ticket requires that pooled content contain **no PII and no tenant-identifying
information**, that a conversation be attributable to its **conversation ID and nothing
further**, and that the ID **not resolve to a tenant/user from within the common area**.
Our earlier scaffold stored `tenant_id` in the analysis record and returned it — this
violates the attribution NFR.

## Decision
- **De-identification is a hard boundary in the ingest/analyze path** (which runs with
  tenant-scoped read access). Before anything is written to the common store we:
  scrub PII from message content **and drop tenant_id / user_id / email / username**.
- The **common store is keyed by `conversation_id` only** and holds: de-identified
  messages, feedback (thumbs + free-text, PII-scrubbed), analysis (category, next step,
  confidence, rationale), metrics, run/status, and override audit — nothing that resolves
  to a tenant or user.
- The read API and UI reference conversations **by ID only**. No tenant filter/column is
  exposed from the common area. Any operational ID→tenant lookup lives **outside** the
  common area and is not reachable from it.

## Consequences
- Remove `tenant_id` from the analysis record + API responses + UI (change vs current
  scaffold).
- Metrics/telemetry are retained; PII scrubbing already exists and is extended to tenant
  identifiers and applied at the de-id boundary, not ad hoc.
- Pooling across tenants becomes permissible because isolation is enforced by de-id.

## Alternatives considered
- Keep tenant_id but gate by RBAC — rejected: the ticket forbids tenant-identifying info
  in the common area regardless of who is viewing.
