# ADR-0002 — LLM decides the category (signals as hints)

**Status:** Accepted (2026-08-11)

## Context
FR-2 requires exactly one of five categories per conversation. A conversation can fire
multiple signals at once (e.g. thumbs-down *and* abandonment), so we need a rule for the
single label. Options: a hard precedence order, primary + secondary labels, or let the
LLM choose.

## Decision
Compute deterministic signals (feedback thumbs, repeated prompts, abandonment, error,
router `intent`, `frustrated`) and pass them to Gemini as **strong hints**; the **LLM
makes the final single-label decision**. Store **all** fired signals alongside the label
for reviewer transparency.

## Consequences
- Simpler than maintaining a brittle precedence table; handles conflicts contextually.
- Requires eval against a human gold set to trust it (see `04-experiments.md` E3).
- The stored signals let reviewers see *why* and let us audit disagreements.

## Alternatives considered
- Hard precedence (`negative > positive > out_of_scope > failed > resolved`) — rejected as
  too rigid; kept as a documented fallback if the LLM proves unreliable.
- Primary + secondary labels — deferred (FR-2 asks for one category; secondary tag may
  return with the J1-93353 richer taxonomy).
