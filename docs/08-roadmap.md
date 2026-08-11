# 08 — Roadmap

Two tracks: the **hackathon MVP** (buildable under current access) and the **production
roadmap** (needs access/infra we don't yet have). Full task detail lives here; status in
`progress.md`.

## Track A — Hackathon MVP (target: 1 day)

### H0 — Smoke tests (de-risk first)
- H0.1 Connect to chat DB (SELECT); read one conversation + messages + feedback.
- H0.2 LangSmith read: `list_runs` by `conversation_id`; fetch a trace; confirm
  tokens + timing (TTFT?).
- H0.3 Gemini call from the service environment.

### H1 — Analyzer core (FR-1/2/3)
- H1.1 Config + secrets; runtime probes for DB + LangSmith (graceful degrade).
- H1.2 Select eligible conversations (≥1 exchange, all tenants, not already analysed).
- H1.3 Transcript assembly + PII scrub / fluff removal.
- H1.4 Deterministic signals (feedback, repeat, abandonment, error, intent/frustration).
- H1.5 Gemini classify → strict JSON (category + next step + rationale + confidence).
- H1.6 Enrich metrics from LangSmith (prompt/input/output tokens + TTFT/latency).
- H1.7 Persist to ResultStore (idempotent on `conversation_id`).

### H2 — Read API (FR-4)
- H2.1 `GET /analysis/conversations` (filters + category counts).
- H2.2 `GET /analysis/conversations/{id}` (analysis + transcript + feedback + metrics).

### H3 — Reviewer surface (core-last)
- H3.1 (A) New tab in `TenantAdministration` reusing `ChatHistory` + `UserFeedbackView`.
- H3.1 (B, fallback) Minimal standalone page / Swagger over the API.

### H4 — Demo
- Run on ~10 real conversations covering all 5 categories; scripted walkthrough.

## Track B — Production roadmap (needs write access / infra)
- Managed, service-owned store + migrations; `analysis_version`/`prompt_version`.
- Event-driven pipeline: completion event + inactivity sweeper + durable queue/worker
  (replace batch polling).
- In-VPC deploy (Cloud Run) so the dashboard calls the API internally; hardened
  `require_admin`.
- Eval: full gold set + accuracy/confusion-matrix harness meeting the bar.
- Reporting layer from J1-93353: high-frequency issues, popular new use-cases, drift rate.
- Optional J1-93353 extras: severity, one-line root-cause, richer error taxonomy as a
  secondary tag.
- Rollout: feature flag + shadow run → reviewer walkthrough → PII/GDPR sign-off.

## Sequencing
`H0 → H1 → H2 → H3 (A if time else B) → H4`. H1.5 prompt work can start on exported
sample transcripts in parallel with H0. Track B follows scope + access confirmation.

## Dependencies / blockers
- **Pending PM:** scope reconciliation (FR-1..4 vs J1-93353) — `progress.md` §Blockers.
- **Credentials:** LangSmith read key; chat DB read-only connection details.
- **Access we lack:** write to any org DB (→ own ResultStore); in-VPC hosting (→ Devin
  Cloud for now).
