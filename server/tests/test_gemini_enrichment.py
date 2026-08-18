"""Guard test: the classifier prompt carries orchestrator + enrichment context, and NEVER a
secret, JWT, URL, or raw personal datum (ADR-0018)."""

from app import gemini
from app import orchestrator_profile as op
from app.enrichment import build_enrichment
from app.domain.models import Conversation, Feedback, Message

_RUN = {
    "tags": ["intent:knowledge_search", "agent:rag", "response_type:answer"],
    "inputs": {"intent": "knowledge_search",
               "reasoning": "User bob@x.com at Crofts Hall asked about req 12345678 for $3,703.85."},
    "outputs": {"agent_used": "rag", "response_type": "answer",
                "citations": [{"file_name": "shopblue_assign-approver.html", "snippet": "x"}]},
    "extra": {"metadata": {"_user_jwt_token": "eyJSECRETjwt", "user_id": "9464669"}},
}


def _conv() -> Conversation:
    c = Conversation(
        id="c1", tenant_id="20020000808", title=None, created_at="2026-01-01T00:00:00",
        feedback=Feedback(), region="us",
        messages=[Message(id="m", role="user", sequence_num=1, created_at="2026-01-01T00:00:00",
                          content="contact me at alice@x.com about req 998877 for $5,000 on 9/1/2026")],
    )
    c.enrichment = build_enrichment([_RUN])  # reasoning is scrubbed at build time
    return c


def test_prompt_has_context_but_no_leaks(monkeypatch):
    monkeypatch.setattr(op, "profile", lambda: "JAI is a procurement assistant. Tools: rag, ticket.")
    monkeypatch.setattr(op, "tenant_rules",
                        lambda tid: "Platform is ShopBlue. Do NOT mention eReq (outdated).")

    prompt = gemini._batch_prompt([_conv()])

    # context is present and useful
    assert "procurement assistant" in prompt
    assert "ShopBlue" in prompt and "eReq" in prompt          # tenant scope rules
    assert "router_intent=knowledge_search" in prompt         # enrichment
    assert "knowledge_base_docs_found=true" in prompt

    # NOTHING sensitive leaks
    for leak in ("eyJSECRETjwt", "_user_jwt_token", "9464669", "bob@x.com", "alice@x.com",
                 "12345678", "998877", "3,703.85", "$5,000", "9/1/2026", "https://"):
        assert leak not in prompt, f"{leak!r} leaked into the LLM prompt"
    # transcript PII was scrubbed to tags instead
    assert "[email]" in prompt and "[id]" in prompt
