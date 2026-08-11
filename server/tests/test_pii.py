"""PII redaction: regex (always) + spaCy NER (when the model is installed)."""

import pytest

from app import pii


def test_regex_redacts_emails_and_phones():
    out = pii.redact("mail me jane@acme.com or +1 555-123-4567")
    assert "jane@acme.com" not in out and "[email]" in out
    assert "555-123-4567" not in out and "[phone]" in out


def test_ner_redacts_person_names_when_model_available():
    if pii._nlp() is None:
        pytest.skip("spaCy model en_core_web_sm not installed")
    out = pii.redact("Please contact John Smith about the invoice")
    assert "John Smith" not in out
    assert "[person]" in out
