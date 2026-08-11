from app.domain.models import Feedback, Message
from app.domain.signals import (
    detect_abandoned,
    detect_error,
    detect_repeated_prompts,
    feedback_signal,
    scrub_pii,
    similarity,
    strip_fluff,
)


def _m(role, content, seq, **extra):
    return Message(id=f"m{seq}", role=role, content=content, sequence_num=seq, **extra)


def test_similarity_identical_and_disjoint():
    assert similarity("a b c", "a b c") == 1.0
    assert similarity("a b", "c d") == 0.0


def test_similarity_ignores_punctuation():
    assert similarity("where is my order", "where is my order??") > 0.9


def test_detect_repeated_prompts():
    assert detect_repeated_prompts(["where is my req", "where is my req?"]) is True
    assert detect_repeated_prompts(["what is an rfp", "how do I approve an invoice"]) is False


def test_detect_abandoned():
    assert detect_abandoned([_m("user", "hi", 1), _m("assistant", "hello", 2), _m("user", "?", 3)]) is True
    assert detect_abandoned([_m("user", "hi", 1), _m("assistant", "hello", 2)]) is False


def test_detect_error():
    assert detect_error([_m("assistant", "x", 1, status="failed")]) is True
    assert detect_error([_m("assistant", "x", 1, error_message="boom")]) is True
    assert detect_error([_m("assistant", "x", 1)]) is False


def test_feedback_signal():
    assert feedback_signal(Feedback(rating=True)) == "positive"
    assert feedback_signal(Feedback(rating=False)) == "negative"
    assert feedback_signal(Feedback(rating=None)) is None


def test_scrub_pii():
    out = scrub_pii("mail jane.doe@acme.com or +1 (555) 123-4567")
    assert "jane.doe@acme.com" not in out
    assert "[email]" in out and "[phone]" in out


def test_strip_fluff():
    out = strip_fluff([_m("assistant", "Welcome to JAI!", 1), _m("assistant", "The answer is 42.", 2)])
    assert len(out) == 1 and "42" in out[0].content
