"""Analyse a conversation into a common-area record (deterministic path)."""

from __future__ import annotations

from datetime import datetime, timezone

from .category import derive_category, recommended_next_step
from .models import AnalysisRecord, Conversation, Metrics, Signals
from .signals import detect_abandoned, detect_error, detect_repeated_prompts, feedback_signal

ANALYZER_VERSION = "0.2.0"


def compute_signals(conv: Conversation) -> Signals:
    user_messages = [m.content for m in conv.messages if m.role == "user"]
    return Signals(
        feedback=feedback_signal(conv.feedback),
        repeated_prompts=detect_repeated_prompts(user_messages),
        abandoned=detect_abandoned(conv.messages),
        error=detect_error(conv.messages),
        out_of_scope_intent=conv.out_of_scope_intent,
        frustrated=conv.frustrated,
    )


def compute_metrics(conv: Conversation) -> Metrics:
    """Per-conversation telemetry. Missing values stay None (AC-7: unavailable, not zero)."""
    assistant = [m for m in conv.messages if m.role == "assistant"]

    def _sum(attr: str) -> int | None:
        present = [v for m in assistant if (v := getattr(m, attr)) is not None]
        return sum(present) if present else None

    ttft = next((m.ttft_ms for m in assistant if m.ttft_ms is not None), None)
    return Metrics(
        ttft_ms=ttft,
        input_tokens=_sum("input_tokens"),
        output_tokens=_sum("output_tokens"),
        prompt_tokens=_sum("prompt_tokens"),
    )


def analyze(conv: Conversation, run_id: str, now: str | None = None) -> AnalysisRecord:
    """
    In production the LLM makes the final category decision with these signals as hints;
    here we use the deterministic derivation. Raises are handled by the run loop (retry).
    """
    signals = compute_signals(conv)
    category = derive_category(signals)
    return AnalysisRecord(
        conversation_id=conv.id,
        model_category=category,
        recommended_next_step=recommended_next_step(category),
        confidence="high" if signals.feedback else "medium",
        rationale=f"Category derived from signals: {signals}.",
        signals=signals,
        metrics=compute_metrics(conv),
        status="analysed",
        run_id=run_id,
        analyzer_version=ANALYZER_VERSION,
        analyzed_at=now or datetime.now(timezone.utc).isoformat(),
    )
