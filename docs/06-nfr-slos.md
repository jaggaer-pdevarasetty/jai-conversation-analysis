# 06 — Non-Functional Requirements & SLOs

From Jira J1-93353 §7. These are binding for the design.

## Cadence (scheduled, not per-conversation)
- A conversation becomes **eligible once inactive for ≥ 5 minutes**.
- Analysis **runs every 4 hours** (batch). A conversation last active < 5 min before a run
  is excluded from that run and picked up by the next (AC-11).

## AI accuracy / quality
- **≥ 85%** agreement with a human reviewer on the assigned category (proposed — confirm).
- **Critical failure:** labelling a *failed* or *out-of-scope* conversation as *resolved*.
- Confusion between adjacent categories is tolerable.
- Measured against a human-labelled gold set (confusion matrix); resolved-mislabel tracked
  separately as a hard gate.

## Security / RBAC
- Access to the common analysis area restricted to **JAI product & internal reviewers**.
- **Pooled, not per-tenant** — reviewers see the pooled population.

## De-identification (the control that permits pooling)
- Content in the common area contains **no tenant-identifying information and no PII**.
- **De-identification happens before** content enters the common area (in the ingest/
  analyze path, which runs with tenant-scoped read access; the common store never receives
  raw identifiers).

## Attribution
- Every conversation and its analysis are attributable to the **conversation ID and
  nothing further**. Reporting references conversations **by ID only**.
- The conversation ID **must not resolve to a tenant or user from within the common area**
  (any ID→tenant mapping, if it exists at all, lives outside the common area and is not
  reachable from it).

## Auditability
- Assigned category, recommended next step, and any **human override** are retained as an
  auditable record against the conversation ID (who/when/old→new for overrides).

## Reliability
- Conversations that **fail analysis are queued and retried in the next run**.
- **Unanalysed counts remain visible** to reviewers — never silently excluded (AC-9).

## Telemetry completeness
- Latency and token counts are captured at generation time (from LangSmith, ADR-0003) and
  retained with the conversation.
- **Missing telemetry is shown as missing/unavailable, not rendered as zero** (AC-7).

## Performance (engineering SLOs, proposed)
- Unit/component + server test suites each green in **< 30s** (fast feedback).
- A scheduled run processes its eligible batch within the 4-hour window with margin.

## Cost
- One LLM call per conversation on filtered/de-identified, summarised input (never raw
  dumps). Add sampling / cheaper-model escalation if full-population volume requires it.

## Internationalisation
- Non-English conversations are still categorised, not excluded (AC-8).
