# ADR-0012 — Conversation sources (fixtures | LangSmith)

**Status:** Accepted (2026-08-11)

## Context
The analyzer needs real conversations. The canonical transcript lives in the private-IP
chat DB (Cloud SQL), unreachable outside the VPC; LangSmith (a public API, with our key)
holds the runs with conversation_id + authoritative tokens/latency + intent/frustration
signals and can reconstruct conversations for analysis now.

## Decision
- A pluggable source selected by `SOURCE` (`fixtures` default, `langsmith`).
- `app/sources.py::load_from_langsmith` resolves the project session, queries
  `/api/v1/runs/query`, and groups runs by `conversation_id` (metadata) into `Conversation`
  objects. Field mapping (inputs/outputs → messages) is **best-effort and isolated** in
  helpers; it must be validated against one real sample. Tokens/latency/`conversation_id`
  are the reliable parts (ADR-0003).
- Uses the env-aware HTTP client (`app/http.py`) → works behind **Zscaler** via the **OS
  trust store** (`truststore`, macOS/Windows) which already trusts the Zscaler root; an
  explicit `REQUESTS_CA_BUNDLE` is honoured when set (Linux/GCP). **TLS is never disabled.**
  (OpenSSL rejects the Zscaler root's non-critical Basic Constraints, so the OS store is the
  robust path locally.)
- `tenant_id` is carried only on the SOURCE side and dropped by de-identification (ADR-0007)
  before the common store.
- Startup never crashes on a source error (logs + empty), so a bad network doesn't wedge the app.

## Consequences
- Real data flows with `SOURCE=langsmith` from GCP, or locally once `REQUESTS_CA_BUNDLE`
  points at the Zscaler root CA. From an un-trusted machine it fails closed with a clear
  `CERTIFICATE_VERIFY_FAILED`.
- The run→message mapping is provisional; confirm against a real LangSmith run, then tighten.
- Later: the chat DB reader can supersede LangSmith for the canonical transcript.
