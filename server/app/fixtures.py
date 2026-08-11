"""Deterministic sample conversations (one per category) with valid UUIDs + metrics.

Real runs read these from the chat DB (SELECT) + LangSmith; fixtures seed the demo/tests.
"""

from __future__ import annotations

from .domain.models import Conversation, Feedback, Message

# A safely-past timestamp so fixtures are always "inactive >= 5 min" and thus eligible.
_TS = "2026-01-01T00:00:00.000Z"


def _assistant(id_: str, content: str, seq: int) -> Message:
    return Message(
        id=id_,
        role="assistant",
        content=content,
        sequence_num=seq,
        created_at=_TS,
        model="gemini-2.5-flash",
        input_tokens=130,
        output_tokens=48,
        prompt_tokens=120,
        ttft_ms=340,
    )


def _user(id_: str, content: str, seq: int) -> Message:
    return Message(id=id_, role="user", content=content, sequence_num=seq, created_at=_TS)


CONVERSATIONS: list[Conversation] = [
    Conversation(
        id="11111111-1111-4111-8111-111111111111",
        tenant_id="20256789",
        title="What is an RFP?",
        created_at=_TS,
        feedback=Feedback(),
        messages=[
            _user("a1000000-0000-4000-8000-000000000001", "What is an RFP?", 1),
            _assistant("a1000000-0000-4000-8000-000000000002", "An RFP (Request for Proposal) solicits supplier proposals.", 2),
        ],
    ),
    Conversation(
        id="22222222-2222-4222-8222-222222222222",
        tenant_id="20256789",
        title="Where is my requisition?",
        created_at=_TS,
        feedback=Feedback(),
        messages=[
            _user("a2000000-0000-4000-8000-000000000001", "Where is my requisition stuck?", 1),
            _assistant("a2000000-0000-4000-8000-000000000002", "Could you share the requisition number?", 2),
            _user("a2000000-0000-4000-8000-000000000003", "Where is my requisition stuck??", 3),
        ],
    ),
    Conversation(
        id="33333333-3333-4333-8333-333333333333",
        tenant_id="20256789",
        title="How do I approve an invoice?",
        created_at=_TS,
        feedback=Feedback(rating=True, comment="Perfect, thanks!", message_id="a3000000-0000-4000-8000-000000000002"),
        messages=[
            _user("a3000000-0000-4000-8000-000000000001", "How do I approve an invoice?", 1),
            _assistant("a3000000-0000-4000-8000-000000000002", "Open the invoice, review the lines, then click Approve.", 2),
        ],
    ),
    Conversation(
        id="44444444-4444-4444-8444-444444444444",
        tenant_id="20256789",
        title="Punch-out not working",
        created_at=_TS,
        feedback=Feedback(rating=False, comment="This did not help.", message_id="a4000000-0000-4000-8000-000000000002"),
        messages=[
            _user("a4000000-0000-4000-8000-000000000001", "My punch-out catalog will not load.", 1),
            _assistant("a4000000-0000-4000-8000-000000000002", "Try clearing your browser cache.", 2),
        ],
    ),
    Conversation(
        id="55555555-5555-4555-8555-555555555555",
        tenant_id="20256789",
        title="Cancel a purchase order via chat",
        created_at=_TS,
        feedback=Feedback(),
        out_of_scope_intent=True,
        messages=[
            _user("a5000000-0000-4000-8000-000000000001", "Cancel purchase order PO-8842 for me.", 1),
            _assistant("a5000000-0000-4000-8000-000000000002", "I can't perform that action; here's how to cancel it in the app.", 2),
        ],
    ),
    # Non-English (AC-8) with MISSING telemetry (AC-7): assistant reply has no tokens/ttft.
    Conversation(
        id="66666666-6666-4666-8666-666666666666",
        tenant_id="20256789",
        title="¿Cómo creo una requisición?",
        created_at=_TS,
        feedback=Feedback(),
        messages=[
            _user("a6000000-0000-4000-8000-000000000001", "¿Cómo creo una requisición de compra?", 1),
            Message(
                id="a6000000-0000-4000-8000-000000000002",
                role="assistant",
                content="Abre Requisiciones, pulsa Crear y completa las líneas.",
                sequence_num=2,
                created_at=_TS,
                model="gemini-2.5-flash",
            ),
        ],
    ),
]

CONVERSATIONS_BY_ID: dict[str, Conversation] = {c.id: c for c in CONVERSATIONS}
