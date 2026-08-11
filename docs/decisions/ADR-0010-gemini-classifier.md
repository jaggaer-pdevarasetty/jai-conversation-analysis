# ADR-0010 — Gemini classifier with deterministic fallback

**Status:** Accepted (2026-08-11)

## Context
FR-2 needs an AI-assigned category. The scaffold classified via deterministic rules only.
We want real LLM classification (Gemini) but the system must stay runnable/testable
without a key and resilient when the model is unavailable (AC-9).

## Decision
- `make_classifier()` returns the **Gemini** classifier when `GEMINI_API_KEY` is set,
  otherwise the **deterministic rules** (`analyze`). Same `(conv, run_id, now)` signature.
- Gemini is called via its REST API with `httpx`; deterministic signals are passed as
  hints. The transcript is **de-identified** before it gets here and is wrapped as
  untrusted DATA with a fixed system prompt (prompt-injection safe). Classifies any
  language (AC-8).
- **Failure handling:** a hard network/API error **raises** → the run loop marks the
  conversation failed and retries next run (AC-9). An unparseable/invalid label **falls
  back** to the deterministic category so a label is always produced.

## Consequences
- No LLM SDK dependency (plain REST via existing `httpx`); mockable in tests.
- Accuracy (≥85%, resolved-mislabel hard gate) is validated by the eval harness (next
  milestone), not assumed.
