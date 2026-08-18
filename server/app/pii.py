"""PII redaction — the single place text is cleaned before it leaves for the LLM or the store.

Two layers:
1. **Regex** (`scrub_pii`): structured PII — emails, phone numbers. Always on, fast, no deps.
2. **NER** (spaCy `en_core_web_sm`): names/places/orgs (PERSON, GPE, LOC, ORG) that regex can't
   catch. Loaded lazily; if spaCy or the model is missing it degrades to regex-only (a warning
   is printed once). NER runs first (sees names in context), then regex catches the rest.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

from .domain.signals import scrub_pii as _regex_redact

# PERSON/GPE/LOC/FAC = names + places/buildings (quasi-identifiers). ORG kept too, but note the
# orchestrator profile / tenant rules are passed SEPARATELY and are NOT run through this (they
# are config, not user data), so platform names like "ShopBlue" survive there for accuracy.
_NER_LABELS = {"PERSON", "GPE", "LOC", "ORG", "FAC"}


def pseudonymize(prefix: str, value) -> str | None:
    """One-way stable pseudonym for an identifier (user id/name/email). Never reversible.
    Lets us group ("same user") without sending the raw identity to the LLM or storing it."""
    if value in (None, ""):
        return None
    digest = hashlib.sha256(f"{prefix}:{value}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


@lru_cache(maxsize=1)
def _nlp():
    try:
        import spacy

        # NER only — disable the pipes we don't need so it stays fast.
        return spacy.load(
            "en_core_web_sm", disable=["tagger", "parser", "lemmatizer", "attribute_ruler"]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] spaCy NER unavailable ({type(exc).__name__}); PII = regex only", flush=True)
        return None


def _ner_redact(text: str) -> str:
    nlp = _nlp()
    if nlp is None or not text.strip():
        return text
    doc = nlp(text)
    spans = [(e.start_char, e.end_char, e.label_) for e in doc.ents if e.label_ in _NER_LABELS]
    # replace from the end so earlier offsets stay valid
    for start, end, label in sorted(spans, key=lambda s: s[0], reverse=True):
        text = f"{text[:start]}[{label.lower()}]{text[end:]}"
    return text


def redact(text: str) -> str:
    """Redact names (NER) then structured PII (regex). Safe to call on any free text."""
    return _regex_redact(_ner_redact(text))
