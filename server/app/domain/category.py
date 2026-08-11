"""Category derivation + recommended next step (FR-2 / FR-3)."""

from __future__ import annotations

from .models import Category, Signals


def derive_category(signals: Signals) -> Category:
    """
    Deterministic fallback + strong prior for the LLM (ADR-0002: the LLM makes the final
    call, signals are hints). Order reflects that explicit feedback is the strongest signal.
    """
    if signals.feedback == "negative":
        return "negative_feedback"
    if signals.feedback == "positive":
        return "positive_feedback"
    if signals.out_of_scope_intent:
        return "out_of_scope"
    if signals.frustrated or signals.repeated_prompts or signals.abandoned or signals.error:
        return "failed_to_resolve"
    return "resolved"


_NEXT_STEP: dict[Category, str] = {
    "positive_feedback": "No action; candidate for the eval golden set.",
    "negative_feedback": "Review the response; candidate for a prompt or KB fix.",
    "failed_to_resolve": "Investigate routing/retrieval; likely a knowledge-base gap.",
    "out_of_scope": "Log as a capability/feature request.",
    "resolved": "No action.",
}


def recommended_next_step(category: Category) -> str:
    return _NEXT_STEP[category]
