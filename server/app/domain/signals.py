"""Deterministic signal extraction — no LLM (evidence-based)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Enrichment, Feedback, Message

_NON_WORD = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace — so 'req' and 'req?' match."""
    return _WS.sub(" ", _NON_WORD.sub(" ", text.lower())).strip()


def similarity(a: str, b: str) -> float:
    """Jaccard word-set similarity in [0, 1]."""
    sa = {w for w in normalize(a).split(" ") if w}
    sb = {w for w in normalize(b).split(" ") if w}
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def detect_repeated_prompts(user_messages: list[str], threshold: float = 0.8) -> bool:
    """Two consecutive near-duplicate user prompts → the user is repeating."""
    for i in range(1, len(user_messages)):
        if similarity(user_messages[i - 1], user_messages[i]) >= threshold:
            return True
    return False


def detect_abandoned(messages: list[Message]) -> bool:
    """The last turn is the user's (no assistant reply) → likely abandoned."""
    return bool(messages) and messages[-1].role == "user"


def detect_error(messages: list[Message]) -> bool:
    """Any DB-level message error: a non-completed status (failed/error/stopped/partial/…)
    or an explicit error_message."""
    return any(
        (m.status is not None and m.status not in ("", "completed"))
        or (m.error_message or "") != ""
        for m in messages
    )


@dataclass(frozen=True)
class AttentionResult:
    reasons: tuple[str, ...] = ()
    kb_issue: bool = False
    guardrail_bypass: bool = False
    source_code: bool = False
    high_frustration: bool = False


_FENCED_BLOCK = re.compile(r"```\s*([A-Za-z0-9_+.#-]*)[^\n]*\n(.*?)```", re.DOTALL)
_CODE_FENCE_EXCLUSIONS = {"", "html", "htm", "markdown", "md", "mdx", "text", "plaintext", "dr-table", "vega-lite"}
_UNLABELLED_CODE = re.compile(
    r"(?:^|\n)\s*(?:def |class |import |from \S+ import |function |const |let |var |SELECT\s|"
    r"INSERT\s|UPDATE\s|DELETE\s|CREATE\s+(?:TABLE|FUNCTION)|#!/|public\s+(?:class|static)|"
    r"using\s+System|package\s+\w+)",
    re.IGNORECASE,
)
_INTERNAL_TECHNICAL = re.compile(
    r"technical proposal|vector store|storage engine|structural profiler|layout-specific chunking|"
    r"metadata promotion|hybrid router|llm escalation|typed tables|templated structured quer|"
    r"system prompt|custom instructions|langgraph|internal architecture|implementation approach",
    re.IGNORECASE,
)
_INTERNAL_DOCUMENT = re.compile(r"^(?:DML-\d+|ADR[-_ ]?\d+|.*(?:architecture|technical[-_ ]?design).*)", re.IGNORECASE)
_REJECT_RESPONSE = "i apologize, but i can only help with procurement-related questions."


def detect_assistant_attention(messages: list[Message], enrichment: Enrichment | None = None) -> AttentionResult:
    assistant = [message for message in messages if message.role == "assistant"]
    texts = [(message.content or "").strip() for message in assistant]
    lowered = [text.lower() for text in texts]
    reasons: list[str] = []

    def add(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    if any("i'm getting too many requests right now" in text or "rate limit" in text or "quota exceeded" in text for text in lowered):
        add("rate_limit")
    if any("that service isn't available right now" in text or "service temporarily unavailable" in text or "i'm having trouble connecting right now" in text for text in lowered):
        add("service_failure")
    if any("something went wrong on my end" in text or "i'm having trouble processing your request" in text or "unable to process your request" in text or "an unexpected error occurred" in text for text in lowered):
        add("processing_failure")
    if any("the response is taking too long" in text or "unable to start response stream" in text or "failed to start response stream" in text or "an error occurred while streaming" in text for text in lowered):
        add("stream_failure")
    if any("i couldn't verify access for that request" in text for text in lowered):
        add("authentication_failure")
    if any(
        "unable to create your support ticket" in text
        or "wasn't able to create the ticket" in text
        or "unable to create the ticket" in text
        or "could not create the ticket" in text
        or "failed to create the ticket" in text
        or "ticket could not be created" in text
        or "ticket was not created" in text
        or "wasn't able to retrieve the ticket status" in text
        or "wasn't able to check the ticket status" in text
        for text in lowered
    ):
        add("ticket_failure")
    if assistant and not texts[-1]:
        add("empty_final_response")

    high_frustration = bool(enrichment and isinstance(enrichment.frustration_score, (int, float)) and enrichment.frustration_score >= 3)
    if high_frustration:
        add("high_frustration")

    docs = enrichment.retrieved_docs if enrichment else []
    internal_document = any(_INTERNAL_DOCUMENT.search(str(document)) for document in docs)
    technical_answer = any(text.lower() != _REJECT_RESPONSE and _INTERNAL_TECHNICAL.search(text) for text in texts)
    rejected_before_answer = any(
        text == _REJECT_RESPONSE and any(later != _REJECT_RESPONSE and _INTERNAL_TECHNICAL.search(later) for later in texts[index + 1 :])
        for index, text in enumerate(lowered)
    )
    guardrail_bypass = bool(technical_answer and (internal_document or rejected_before_answer))
    if guardrail_bypass:
        add("guardrail_bypass")

    source_code = False
    for text in texts:
        for match in _FENCED_BLOCK.finditer(text):
            language = (match.group(1) or "").lower()
            if language not in _CODE_FENCE_EXCLUSIONS or (not language and _UNLABELLED_CODE.search(match.group(2))):
                source_code = True
                add("source_code")
                break
        if source_code:
            break

    technical_error = re.compile(
        r"Traceback \(most recent call last\)|File \"[^\"]+\", line \d+|"
        r"\b(?:ValueError|TypeError|RuntimeError|KeyError|AttributeError|ImportError|DatabaseError):"
    )
    if any(technical_error.search(text) for text in texts):
        add("technical_error_leak")

    kb_issue = any(
        "couldn't find relevant information" in text
        or "no results found" in text
        or "unable to answer" in text
        or "cannot answer" in text
        or "couldn't answer" in text
        for text in lowered
    )
    if detect_error(messages):
        add("message_error")
    return AttentionResult(tuple(reasons), kb_issue, guardrail_bypass, source_code, high_frustration)


def feedback_signal(fb: Feedback) -> str | None:
    if fb.rating is True:
        return "positive"
    if fb.rating is False:
        return "negative"
    return None


_PII = [
    (re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE), "[email]"),
    (re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), "[iban]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[card]"),  # 13-19 digit card-like sequences
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[ip]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ssn]"),
]

# Quasi-identifiers: values that alone aren't PII but combined can re-identify a person
# (dates + amounts + reference numbers/codes). Blurred to cut re-identification risk while
# keeping the topic intact — the classifier needs "a requisition number", not the number.
_QUASI = [
    (re.compile(r"[$€£₹]\s?\d[\d.,]*\b"), "[amount]"),  # $3,703.85 / €1.200,50
    (re.compile(r"\b\d[\d.,]*\s?(?:USD|EUR|GBP|INR|CAD|AUD)\b", re.IGNORECASE), "[amount]"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[date]"),  # 2026-08-12
    (re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"), "[date]"),  # 8/12/2026
    (re.compile(
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",
        re.IGNORECASE), "[date]"),  # Aug 12, 2026
    (re.compile(
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}\b",
        re.IGNORECASE), "[date]"),  # 12 August 2026
    # Reference codes: a letter prefix + a hyphen + a LONG digit run (>=5), e.g. PO-000123,
    # REQ-1234567. The long digit run is what makes it identifier-like, so ordinary
    # product/version names (COVID-19, UTF-8, SAP-2000, HTTP-500, gemini-2.5) are left intact.
    (re.compile(r"\b[A-Za-z]{2,}-\d{5,}\b"), "[id]"),
]

# Broad catch-alls LAST so they don't eat the specific matches above.
_PII_TAIL = [
    (re.compile(r"\+?\d[\d ().-]{7,}\d"), "[phone]"),
    (re.compile(r"\b\d{6,}\b"), "[id]"),  # long bare number (requisition/PO/order id)
]


def scrub_pii(text: str) -> str:
    """Redact PII + quasi-identifiers before any text is sent to the LLM or stored."""
    out = text
    for pattern, tag in [*_PII, *_QUASI, *_PII_TAIL]:
        out = pattern.sub(tag, out)
    return out


_FLUFF = [re.compile(r"^welcome to", re.I), re.compile(r"^hi[!,. ]", re.I), re.compile(r"how can i help", re.I)]


def strip_fluff(messages: list[Message]) -> list[Message]:
    """Drop assistant greeting/welcome fluff so the LLM sees the substantive exchange."""
    return [
        m
        for m in messages
        if not (m.role == "assistant" and any(f.search(m.content.strip()) for f in _FLUFF))
    ]
