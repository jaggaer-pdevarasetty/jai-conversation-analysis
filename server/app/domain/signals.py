"""Deterministic signal extraction — no LLM (evidence-based)."""

from __future__ import annotations

import re

from .models import Feedback, Message

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
    return any(m.status == "failed" or (m.error_message or "") != "" for m in messages)


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
