"""Domain types for conversation analysis (J1-93353).

Two sides, separated on purpose (ADR-0007):
- **Source** side (`Conversation`) is read from the chat DB with tenant scope and MAY
  carry identifiers. It never leaves the ingest/de-identify path.
- **Common** side (`AnalysisRecord`, `CommonConversation`) is what enters the pooled
  common area: keyed by conversation_id ONLY, de-identified, no tenant/user.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Role = Literal["system", "user", "assistant", "live_agent"]

Category = Literal[
    "resolved",
    "failed_to_resolve",
    "positive_feedback",
    "negative_feedback",
    "out_of_scope",
]

CATEGORIES: tuple[Category, ...] = (
    "resolved",
    "failed_to_resolve",
    "positive_feedback",
    "negative_feedback",
    "out_of_scope",
)

Confidence = Literal["high", "medium", "low"]
Status = Literal["analysed", "failed", "pending"]


@dataclass
class Message:
    id: str
    role: Role
    content: str
    sequence_num: int
    status: Optional[str] = None
    error_message: Optional[str] = None
    model: Optional[str] = None
    created_at: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    ttft_ms: Optional[int] = None


@dataclass
class Feedback:
    rating: Optional[bool] = None  # True=up, False=down, None=none
    comment: Optional[str] = None


# ── Source side (pre-de-identification; carries identifiers) ─────────────────
@dataclass
class Conversation:
    id: str
    tenant_id: str
    title: Optional[str]
    created_at: str
    messages: list[Message]
    feedback: Feedback
    # Hints sourced from LangSmith (router intent / frustration) in production.
    out_of_scope_intent: bool = False
    frustrated: bool = False


@dataclass
class Signals:
    feedback: Optional[Literal["positive", "negative"]]
    repeated_prompts: bool
    abandoned: bool
    error: bool
    out_of_scope_intent: bool
    frustrated: bool


@dataclass
class Metrics:
    """Per-conversation telemetry (ADR: TTFT per conversation). None = unavailable (AC-7)."""

    ttft_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None


@dataclass
class Override:
    category: Category
    actor: str
    at: str


@dataclass
class DeepAnalysis:
    """Extra, deeper analysis kept ONLY for conversations with explicit user feedback.
    `what_happened` and `why_it_happened` are deliberately separate (fact vs root cause)."""

    what_happened: str = ""
    why_it_happened: str = ""
    how_to_avoid: str = ""
    suggestions: str = ""
    user_remark: str = ""  # the user's own feedback comment, verbatim (de-identified)


# ── Common side (pooled area; conversation_id only, de-identified) ───────────
@dataclass
class AnalysisRecord:
    conversation_id: str
    model_category: Category  # original model/derived label (audit)
    recommended_next_step: str
    confidence: Confidence
    rationale: str
    signals: Signals
    metrics: Metrics
    status: Status
    run_id: str
    analyzer_version: str
    analyzed_at: str
    override: Optional[Override] = None
    deep: Optional[DeepAnalysis] = None  # populated only when the conversation has feedback

    @property
    def category(self) -> Category:
        """Effective category — the human override wins over the model label."""
        return self.override.category if self.override else self.model_category


@dataclass
class CommonConversation:
    """De-identified transcript retained in the common area (no tenant/user)."""

    conversation_id: str
    messages: list[Message]
    feedback: Feedback


@dataclass
class RunSummary:
    run_id: str
    started_at: str
    completed_at: str
    analysed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def unanalysed(self) -> int:
        return self.failed
