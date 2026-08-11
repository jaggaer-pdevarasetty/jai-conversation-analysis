# ADR-0010 — Gemini classification via Vertex AI (enterprise), with rules fallback

**Status:** Accepted (2026-08-11; revised — Vertex only)

## Context
FR-2 needs an AI-assigned category. We are enterprise → **Vertex AI only** (no Google AI
Studio). A live probe confirmed Vertex **rejects API keys**
(`401 UNAUTHENTICATED — API keys are not supported by this API; expected OAuth2`). Vertex
requires **OAuth2 via a service account / ADC** plus **project** and **location**.

## Decision
- Classify via the **google-genai SDK in Vertex mode**:
  `genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION)`,
  authenticating through **ADC / `GOOGLE_APPLICATION_CREDENTIALS`** (service account).
- `make_classifier()` uses Vertex **only when project + location are configured**; otherwise
  the **deterministic rules** run — so the app is always populated/testable (and a missing/
  wrong credential doesn't blank the UI).
- The SDK call is injected (`generate`) so tests never touch the network/SDK.
- Transcript is de-identified + wrapped as untrusted DATA (prompt-injection safe); any
  language (AC-8). Hard API failure raises → run retries (AC-9); invalid label → rules fallback.
- Corporate proxy/CA (Zscaler) handled by **env only** (`REQUESTS_CA_BUNDLE`, `HTTPS_PROXY`);
  TLS verification is never disabled.

## Consequences
- To enable real classification you must set `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
  and `GOOGLE_APPLICATION_CREDENTIALS` (SA with **Vertex AI User**). An API key alone won't work.
- Accuracy (≥85%, resolved-mislabel hard gate) is validated by the eval harness (next), not assumed.
