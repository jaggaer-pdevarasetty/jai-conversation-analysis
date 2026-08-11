# ADR-0011 — Evaluation harness + accuracy hard gate

**Status:** Accepted (2026-08-11)

## Context
J1-93353 §7 requires **≥85% category agreement** with a human, and makes labelling a
*failed*/*out-of-scope* conversation as *resolved* a **critical failure** (adjacent-category
confusion tolerated). We need a repeatable way to measure this and gate the classifier.

## Decision
- `app/eval.py`: `evaluate(classifier, conversations, gold) -> EvalReport` computes agreement
  %, a confusion matrix, and **critical failures** (true failed/out_of_scope predicted
  resolved). `passed(threshold=0.85)` = agreement ≥ threshold AND zero critical failures.
- A human **gold set** (`GOLD`) maps conversation_id → expected category; start with the
  fixtures, grow to 100–200 real conversations for a meaningful measurement.
- CLI: `python -m app.eval` runs against the configured classifier (Vertex when configured,
  else deterministic rules) and exits non-zero on failure — usable as a CI/quality gate.
- Deterministic unit tests validate the harness against the rules baseline and prove the
  critical-failure gate trips on a "resolved-everything" classifier.

## Consequences
- Prompt/classifier changes are measured, not assumed. The classifier prompt was tuned so
  explicit thumbs feedback wins (→ positive/negative_feedback); live Vertex eval then scored
  100% on the fixture gold set.
- The 6-fixture gold set is a placeholder; real accuracy needs a larger labelled set (next).
