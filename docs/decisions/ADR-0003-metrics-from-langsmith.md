# ADR-0003 — Source token & latency metrics from LangSmith

**Status:** Accepted (2026-08-11), pending E2 confirmation on a real trace

## Context
FR-4 needs per-message **input/output/prompt tokens** and **time-to-first-token (TTFT)**.
Verified in the chat DB: `messages` has input/output/total tokens and `token_usage` has
`by_model`/`breakdown`/`elapsed_seconds`, but **TTFT is not persisted** (only logged in
`streaming_handler.py`) and **"prompt tokens" is not a distinct column**. Instrumenting
the product to persist these is out of scope (read-only, no write, hackathon).

## Decision
Use **LangSmith** as the authoritative source for token counts (incl. `prompt_token_count`
from Gemini usage metadata) and timing; use the chat DB for transcript + feedback. If a
real trace lacks first-token timing, display **total latency** with an explicit
"TTFT not captured" rather than a misleading value.

## Consequences
- Accurate tokens/latency without touching the product or the DB.
- Bounded by LangSmith's **15-day retention**: older conversations lose these metrics and
  are labelled from transcript only (reduced confidence).
- E2 (`04-experiments.md`) must confirm TTFT + prompt-token presence on a live trace; this
  ADR is updated with the finding.

## Alternatives considered
- Instrument `streaming_handler.py` to persist TTFT — deferred to the production roadmap
  (needs write access + a deploy).
- Approximate prompt tokens = input tokens — kept only as a labelled fallback.
