"""Batched Vertex analyzer — SDK injected (no live calls). Verifies DYNAMIC output."""

import json
import re

from app import gemini
from app.domain.models import Conversation, Feedback, Message
from app.fixtures import CONVERSATIONS


def _generate_dynamic(prompt: str) -> str:
    # One JSON object per conversation_id found in the batch prompt, with CUSTOM fields.
    ids = re.findall(r"conversation_id: (\S+)", prompt)
    return json.dumps(
        [
            {
                "conversation_id": cid,
                "category": "out_of_scope",
                "confidence": "high",
                "recommended_next_step": f"Custom step for {cid[:4]}",
                "rationale": "grounded in the transcript",
            }
            for cid in ids
        ]
    )


def test_batch_uses_dynamic_llm_recommendation_and_confidence():
    recs = gemini.analyze_batch_vertex(CONVERSATIONS[:3], "run", "t", generate=_generate_dynamic)
    assert len(recs) == 3
    by_id = {r.conversation_id: r for r in recs}
    for c in CONVERSATIONS[:3]:
        r = by_id[c.id]
        assert r.model_category == "out_of_scope"
        assert r.recommended_next_step.startswith("Custom step")  # dynamic, not a per-category lookup
        assert r.rationale == "grounded in the transcript"
        assert r.analyzer_version.startswith("vertex:")
        # Calibration: the LLM said "high", but HIGH only survives with explicit feedback.
        assert r.confidence == ("high" if c.feedback.rating is not None else "medium")


def test_high_confidence_requires_explicit_feedback():
    """A high-confidence label with no thumb is capped to medium (no over-confident 'resolved')."""
    no_fb = next(c for c in CONVERSATIONS if c.feedback.rating is None)
    with_fb = next(c for c in CONVERSATIONS if c.feedback.rating is not None)

    def gen_high(prompt: str) -> str:
        if "what_happened" in prompt:  # deep-analysis call for the feedback conversation
            return "{}"
        ids = re.findall(r"conversation_id: (\S+)", prompt)
        return json.dumps(
            [{"conversation_id": cid, "category": "resolved", "confidence": "high",
              "recommended_next_step": "No action needed.", "rationale": "r"} for cid in ids]
        )

    assert gemini.analyze_batch_vertex([no_fb], "r", "t", generate=gen_high)[0].confidence == "medium"
    assert gemini.analyze_batch_vertex([with_fb], "r", "t", generate=gen_high)[0].confidence == "high"


def test_batch_makes_one_call_per_batch_size():
    batch_calls = {"n": 0}

    def counting(prompt: str) -> str:
        if "what_happened" in prompt:  # a deep-analysis call, not a batch call
            return "{}"
        batch_calls["n"] += 1
        return _generate_dynamic(prompt)

    gemini.analyze_batch_vertex(CONVERSATIONS, "run", "t", generate=counting, batch_size=3)
    # 6 fixtures, batch_size 3 → 2 batch calls (not 6); deep calls are separate
    assert batch_calls["n"] == 2


def test_batch_soft_fallback_to_rules_when_entry_missing():
    recs = gemini.analyze_batch_vertex(CONVERSATIONS[:2], "run", "t", generate=lambda _p: "[]")
    assert len(recs) == 2  # still a record each (deterministic fallback)


def test_batch_group_hard_failure_omits_conversations():
    def boom(_p: str) -> str:
        raise RuntimeError("vertex down")

    assert gemini.analyze_batch_vertex(CONVERSATIONS[:3], "run", "t", generate=boom) == []


def test_make_batch_analyzer_defaults_to_rules_without_vertex():
    assert gemini.make_batch_analyzer() is gemini.analyze_batch_rules


def test_feedback_conversation_gets_deep_analysis():
    conv = next(c for c in CONVERSATIONS if c.feedback.rating is not None)

    def gen(prompt: str) -> str:
        if "what_happened" in prompt:  # the deep-analysis prompt
            return json.dumps(
                {"what_happened": "assistant misunderstood", "why_it_happened": "KB gap",
                 "how_to_avoid": "add KB article", "suggestions": "improve routing"}
            )
        return json.dumps(
            [{"conversation_id": conv.id, "category": "negative_feedback", "confidence": "high",
              "recommended_next_step": "fix", "rationale": "r"}]
        )

    rec = gemini.analyze_batch_vertex([conv], "run", "t", generate=gen)[0]
    assert rec.deep is not None
    assert rec.deep.what_happened == "assistant misunderstood"
    assert rec.deep.why_it_happened == "KB gap"  # root cause kept separate from what happened
    assert rec.deep.how_to_avoid and rec.deep.suggestions


def test_pii_is_scrubbed_before_reaching_the_llm():
    conv = Conversation(
        id="p1", tenant_id="t", title=None, created_at="2020-01-01T00:00:00", feedback=Feedback(),
        messages=[
            Message(
                id="m1", role="user", sequence_num=1, created_at="2020-01-01T00:00:00",
                content="email me at john.doe@acme.com or call +1 555-123-4567 please",
            )
        ],
    )
    captured: dict = {}

    def capturing(prompt: str) -> str:
        captured["prompt"] = prompt
        return json.dumps(
            [{"conversation_id": "p1", "category": "resolved", "confidence": "low",
              "recommended_next_step": "No action needed.", "rationale": "ok"}]
        )

    gemini.analyze_batch_vertex([conv], "run", "t", generate=capturing)
    prompt = captured["prompt"]
    assert "john.doe@acme.com" not in prompt  # raw PII must NOT reach the LLM
    assert "555-123-4567" not in prompt
    assert "[email]" in prompt and "[phone]" in prompt
