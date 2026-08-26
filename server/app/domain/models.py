"""Domain types for conversation analysis (J1-93353).

Two sides, separated on purpose (ADR-0007):
- **Source** side (`Conversation`) is read from the chat DB with tenant scope and MAY
  carry identifiers. It never leaves the ingest/de-identify path.
- **Common** side (`AnalysisRecord`, `CommonConversation`) is what enters the pooled
  common area: keyed by conversation_id ONLY, de-identified, no tenant/user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    message_id: Optional[str] = None


# ── Source side (pre-de-identification; carries identifiers) ─────────────────
@dataclass
class Conversation:
    id: str
    tenant_id: str
    title: Optional[str]
    created_at: str
    messages: list[Message]
    feedback: Feedback  # primary feedback (first / most-significant) — kept for back-compat
    feedbacks: list[Feedback] = field(default_factory=list)  # ALL feedback in the chat (ADR-0022)
    user_id: str = ""  # source-side only; pseudonymised before it reaches the common store
    region: str = ""  # source region label (us/eu/uk) — carried through to the record
    environment: str = "uit"  # source environment (uit/prod) — carried through to the record
    # Hints sourced from LangSmith (router intent / frustration) in production.
    out_of_scope_intent: bool = False
    frustrated: bool = False
    # Orchestrator + LangSmith enrichment (safe/scrubbed), attached before analysis.
    enrichment: "Optional[Enrichment]" = None


@dataclass
class Signals:
    feedback: Optional[Literal["positive", "negative"]]
    repeated_prompts: bool
    abandoned: bool
    error: bool
    out_of_scope_intent: bool
    frustrated: bool


@dataclass
class Enrichment:
    """Safe, PII-scrubbed signals from the JAI orchestrator + LangSmith traces (ADR-0018).

    Everything here is either non-personal metadata (intent, agent, flags) or free text that
    has already been PII/quasi-identifier scrubbed. Secrets (JWT/keys/URLs) and raw identifiers
    are NEVER stored here — see enrichment.py / orchestrator_profile.py."""

    intent: Optional[str] = None            # router intent, e.g. knowledge_search
    secondary_intent: Optional[str] = None
    agent_used: Optional[str] = None        # rag / ticket / ticket_status / ...
    response_type: Optional[str] = None     # answer / refusal / handoff
    source_confidence: Optional[str] = None  # the agent's own confidence (HIGH/MEDIUM/LOW)
    retrieval_hit: Optional[bool] = None    # did the knowledge base return any docs?
    retrieved_count: int = 0
    retrieved_docs: list[str] = field(default_factory=list)  # doc file names (identifiers)
    retrieved_snippets: list[str] = field(default_factory=list)  # PII-scrubbed doc snippets (ADR-0021)
    invocation_prompt: str = ""             # PII-scrubbed actual invocation prompt (Tier-2 / feedback; ADR-0021)
    reasoning_summary: str = ""             # scrubbed + truncated agent reasoning ("model thinking")
    frustration_score: Optional[float] = None
    guardrail: Optional[str] = None         # refusal/handoff/guardrail note
    had_error: Optional[bool] = None
    turns: Optional[int] = None
    tenant_rules_applied: bool = False      # were tenant scope rules available for this convo?
    langsmith_found: bool = False           # did we actually match a LangSmith trace?


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
    root_cause: str = ""  # structured root-cause label for grouping (ADR-0022) — enum, no PII


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
    region: str = ""  # which regional source this came from (us/eu/uk) — for analytics
    environment: str = "uit"  # which environment this came from (uit/prod) — strict isolation
    tenant_id: str = ""  # kept for tenant analytics (a company, not a person)
    user_hash: str = ""  # one-way pseudonym of the source user (ADR-0022) — for distinct-user
    #                      impact counts only; non-reversible, never resolves to a user
    override: Optional[Override] = None
    deep: Optional[DeepAnalysis] = None  # populated only when the conversation has feedback
    enrichment: Optional[Enrichment] = None  # safe/scrubbed orchestrator + LangSmith signals

    @property
    def category(self) -> Category:
        """Effective category — the human override wins over the model label."""
        return self.override.category if self.override else self.model_category


@dataclass
class CommonConversation:
    """De-identified transcript retained in the common area (no tenant/user)."""

    conversation_id: str
    messages: list[Message]
    feedback: Feedback  # primary feedback (first / most-significant) — kept for back-compat
    environment: str = "uit"  # env this transcript belongs to (uit/prod) — strict isolation
    feedbacks: list[Feedback] = field(default_factory=list)  # ALL feedback in the chat (ADR-0022)


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
