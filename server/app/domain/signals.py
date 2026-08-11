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
    (re.compile(r"\+?\d[\d ().-]{7,}\d"), "[phone]"),  # keep last: broadest digit run
]


def scrub_pii(text: str) -> str:
    """Redact obvious PII before any text is sent to the LLM."""
    out = text
    for pattern, tag in _PII:
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
