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

## Next 30% (from ~70% → production-ready) — 3 phases, ~10% each

Current state: real chat-DB source, dynamic batched Gemini analysis (PII scrubbed via
regex + spaCy NER before the LLM), Postgres store, batch + on-demand + lazy analyse,
reviewer dashboard (tenant→user→conversation + detail + override). What is left:

### Phase A — Run itself + full coverage (AC-1, AC-9, AC-11) ~10%
- **Scheduler**: APScheduler job every 4h → analyse ALL eligible, not-yet-analysed convos,
  paginated by a `last_message_at` watermark (not a fixed CHATDB_LIMIT). Overlap-safe.
- **Coverage/freshness**: incremental sweeps so 100% get analysed over time; re-analyse
  policy on `analyzer_version`/prompt bumps (backfill job).
- **Reliability**: exponential-backoff retry, a dead-letter after N failures, `/readiness`
  probe, graceful degrade when Vertex/chat-DB is down (already fail-safe; formalise).

### Phase B — Trustworthy (accuracy + auth + privacy + observability) ~10%
- **Eval gold set**: 100–200 human-labelled real conversations; wire `app.eval` into CI;
  enforce ≥85% agreement + zero critical mislabels (resolved-vs-failed) — hard gate.
- **AuthN/AuthZ**: real reviewer SSO/JWT; enforce the RBAC gate; audit overrides (who/when).
- **Privacy governance**: resolve the tenant/user view vs AC-10 de-id (config: admin vs
  pooled mode); Presidio-grade PII pass + a privacy/GDPR sign-off checklist.
- **Observability**: structured logs, Prometheus metrics (runs, latency, failures, cost),
  alerting; a lightweight reporting view (top issues, new use-cases, drift) from J1-93353.

### Phase C — Deployable at scale ~10%
- **Packaging/CI-CD**: Dockerfiles (client+server), pipeline (lint/type/test/contract/e2e),
  secrets via GCP Secret Manager, Alembic migrations for the results store.
- **In-VPC deploy** (Cloud Run) so the chat DB is reachable without a personal login; use a
  dedicated **read-only service account**; TTFT instrumentation with the orchestrator team.
- **Performance/scale**: fix dashboard N+1 (batch store lookups), DB indexes + pooling,
  a durable queue/worker for analysis, response caching; OpenAPI **contract tests** +
  Playwright **e2e** for the reviewer flow.

> UI productionisation (redesign, filters, search, pagination, a11y) is tracked in the
> separate UI session; the backend contracts above are built to support it.

## Sequencing
`H0 → H1 → H2 → H3 (A if time else B) → H4`. H1.5 prompt work can start on exported
sample transcripts in parallel with H0. Track B follows scope + access confirmation.

## Dependencies / blockers
- **Pending PM:** scope reconciliation (FR-1..4 vs J1-93353) — `progress.md` §Blockers.
- **Credentials:** LangSmith read key; chat DB read-only connection details.
- **Access we lack:** write to any org DB (→ own ResultStore); in-VPC hosting (→ Devin
  Cloud for now).
