from app.domain.models import Enrichment, Feedback, Message
from app.domain.signals import (
    detect_abandoned,
    detect_assistant_attention,
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
    assert detect_error([_m("assistant", "x", 1, status="error")]) is True
    assert detect_error([_m("assistant", "x", 1, status="stopped")]) is True
    assert detect_error([_m("assistant", "x", 1, status="partial")]) is True
    assert detect_error([_m("assistant", "x", 1, status="completed")]) is False
    assert detect_error([_m("assistant", "x", 1, error_message="boom")]) is True
    assert detect_error([_m("assistant", "x", 1)]) is False


def test_attention_flags_message_error_from_db_status():
    flagged = detect_assistant_attention([
        _m("user", "show my top supplier", 1),
        _m("assistant", "answer", 2, status="failed", error_message="upstream 500"),
    ])
    assert "message_error" in flagged.reasons

    ok = detect_assistant_attention([_m("assistant", "fine", 1, status="completed")])
    assert "message_error" not in ok.reasons


def test_attention_detects_operational_failures_and_final_empty_response():
    rate = detect_assistant_attention([_m("assistant", "I'm getting too many requests right now. Let's wait a moment or try something else.", 1)])
    assert rate.reasons == ("rate_limit",)
    empty = detect_assistant_attention([_m("assistant", "answer", 1), _m("assistant", "", 2)])
    assert "empty_final_response" in empty.reasons
    intermediate = detect_assistant_attention([_m("assistant", "", 1), _m("assistant", "answer", 2)])
    assert "empty_final_response" not in intermediate.reasons


def test_attention_routes_no_answer_to_kb_without_immediate_flag():
    result = detect_assistant_attention([_m("assistant", "I couldn't find relevant information in our knowledge base for this query.", 1)])
    assert result.kb_issue is True
    assert result.reasons == ()


def test_attention_detects_jai_side_guardrail_bypass_only():
    messages = [
        _m("assistant", "I apologize, but I can only help with procurement-related questions.", 1),
        _m("assistant", "The technical proposal uses a vector store and hybrid router.", 2),
    ]
    enrichment = Enrichment(retrieved_docs=["DML-101656-xlsx-csv-rag-approaches.pdf"])
    result = detect_assistant_attention(messages, enrichment)
    assert result.guardrail_bypass is True
    assert "guardrail_bypass" in result.reasons
    respected = detect_assistant_attention([messages[0], messages[0]], Enrichment())
    assert respected.guardrail_bypass is False
    assert respected.reasons == ()


def test_attention_flags_source_code_but_allows_rendering_and_markup():
    python = detect_assistant_attention([_m("assistant", "```python\nprint('x')\n```", 1)])
    assert python.source_code is True
    for language in ("html", "md", "markdown", "dr-table", "vega-lite"):
        allowed = detect_assistant_attention([_m("assistant", f"```{language}\nvalue\n```", 1)])
        assert allowed.source_code is False


def test_attention_uses_frustration_score_three_as_threshold():
    low = detect_assistant_attention([], Enrichment(frustration_score=2))
    high = detect_assistant_attention([], Enrichment(frustration_score=3))
    assert low.high_frustration is False
    assert high.high_frustration is True
    assert "high_frustration" in high.reasons


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
