"""Batched Vertex analyzer — SDK injected (no live calls). Verifies DYNAMIC output."""

import json
import re

from app import gemini
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
    for r in recs:
        assert r.model_category == "out_of_scope"
        assert r.confidence == "high"  # from the LLM, not a static heuristic
        assert r.recommended_next_step.startswith("Custom step")  # dynamic, not a per-category lookup
        assert r.rationale == "grounded in the transcript"
        assert r.analyzer_version.startswith("vertex:")


def test_batch_makes_one_call_per_batch_size():
    calls = {"n": 0}

    def counting(prompt: str) -> str:
        calls["n"] += 1
        return _generate_dynamic(prompt)

    gemini.analyze_batch_vertex(CONVERSATIONS, "run", "t", generate=counting, batch_size=3)
    # 6 fixtures, batch_size 3 → 2 calls (not 6)
    assert calls["n"] == 2


def test_batch_soft_fallback_to_rules_when_entry_missing():
    recs = gemini.analyze_batch_vertex(CONVERSATIONS[:2], "run", "t", generate=lambda _p: "[]")
    assert len(recs) == 2  # still a record each (deterministic fallback)


def test_batch_group_hard_failure_omits_conversations():
    def boom(_p: str) -> str:
        raise RuntimeError("vertex down")

    assert gemini.analyze_batch_vertex(CONVERSATIONS[:3], "run", "t", generate=boom) == []


def test_make_batch_analyzer_defaults_to_rules_without_vertex():
    assert gemini.make_batch_analyzer() is gemini.analyze_batch_rules
