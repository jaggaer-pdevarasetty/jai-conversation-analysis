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
        # Calibration: an explicit thumb IS the feedback category by definition (FR-2 table),
        # so the model's raw label only survives on conversations WITHOUT explicit feedback.
        if c.feedback.rating is True:
            assert r.model_category == "positive_feedback"
        elif c.feedback.rating is False:
            assert r.model_category == "negative_feedback"
        else:
            assert r.model_category == "out_of_scope"
        # the model's dynamic step survives only where its label survived; a recalibrated
        # category gets the enforced category's step (category and remediation must agree)
        if r.model_category == "out_of_scope":
            assert r.recommended_next_step.startswith("Custom step")  # dynamic, not a lookup
        else:
            assert not r.recommended_next_step.startswith("Custom step")
        assert r.rationale == "grounded in the transcript"
        assert r.analyzer_version.startswith("vertex:")
        # Calibration: the LLM said "high", but HIGH only survives with explicit feedback.
        assert r.confidence == ("high" if c.feedback.rating is not None else "medium")


def test_explicit_thumbs_feedback_wins_over_the_model_label():
    """FR-2 category table: a thumbs-down IS explicit negative feedback (and thumbs-up positive)
    BY DEFINITION — the documented precedence is enforced even when the model returns a
    failure/out-of-scope label (found via the live eval: the lite model under-weighted it).
    A recalibrated category must NOT keep the step the model wrote for the rejected label."""
    from app.domain.category import recommended_next_step

    thumbs_down = next(c for c in CONVERSATIONS if c.feedback.rating is False)
    thumbs_up = next(c for c in CONVERSATIONS if c.feedback.rating is True)

    def gen_wrong(prompt: str) -> str:
        if "what_happened" in prompt:  # deep-analysis call for the feedback conversation
            return "{}"
        ids = re.findall(r"conversation_id: (\S+)", prompt)
        return json.dumps(
            [{"conversation_id": cid, "category": "failed_to_resolve", "confidence": "high",
              "recommended_next_step": "fix the retrieval gap", "rationale": "r"} for cid in ids]
        )

    recs = gemini.analyze_batch_vertex([thumbs_down, thumbs_up], "run", "t", generate=gen_wrong)
    assert [r.model_category for r in recs] == ["negative_feedback", "positive_feedback"]
    # category and remediation must agree: the model's step (written for failed_to_resolve)
    # is replaced by the enforced category's step, not kept alongside the new label
    assert [r.recommended_next_step for r in recs] == [
        recommended_next_step("negative_feedback"),
        recommended_next_step("positive_feedback"),
    ]


def test_mixed_thumbs_ratings_are_left_to_the_model():
    """ADR-0022 multi-feedback: when a conversation has BOTH a thumbs-down and a later
    thumbs-up, the deterministic guard stands down — the model sees the full feedback
    summary and its judgement (either way) must survive."""
    from dataclasses import replace

    from app.domain.models import Feedback

    base = next(c for c in CONVERSATIONS if c.feedback.rating is None)
    mixed = replace(
        base,
        feedback=Feedback(rating=False, comment="wrong"),
        feedbacks=[Feedback(rating=False, comment="wrong"), Feedback(rating=True)],
    )

    def gen(prompt: str) -> str:
        if "what_happened" in prompt:
            return "{}"
        return json.dumps(
            [{"conversation_id": mixed.id, "category": "resolved", "confidence": "medium",
              "recommended_next_step": "model step", "rationale": "later thumb corrected it"}]
        )

    rec = gemini.analyze_batch_vertex([mixed], "run", "t", generate=gen)[0]
    assert rec.model_category == "resolved"  # NOT forced to negative_feedback
    assert rec.recommended_next_step == "model step"  # model's step kept (no recalibration)


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
