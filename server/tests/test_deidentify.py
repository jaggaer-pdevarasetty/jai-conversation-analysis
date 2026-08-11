from app.deidentify import deidentify
from app.domain.models import Conversation, Feedback, Message


def _conv() -> Conversation:
    return Conversation(
        id="c-1",
        tenant_id="20256789",
        title="Acme Corp issue",
        created_at="2026-08-11T09:00:00Z",
        feedback=Feedback(rating=False, comment="call me at jane@acme.com"),
        messages=[
            Message(id="m1", role="user", content="email me at bob@acme.com", sequence_num=1),
            Message(id="m2", role="assistant", content="Sure.", sequence_num=2),
        ],
    )


def test_deidentify_produces_conversation_id_only_record():
    common = deidentify(_conv())
    # CommonConversation has no tenant/title/user fields at all.
    assert not hasattr(common, "tenant_id")
    assert not hasattr(common, "title")
    assert common.conversation_id == "c-1"


def test_deidentify_scrubs_pii_from_content_and_feedback():
    common = deidentify(_conv())
    assert "bob@acme.com" not in common.messages[0].content
    assert "[email]" in common.messages[0].content
    assert common.feedback.comment is not None
    assert "jane@acme.com" not in common.feedback.comment
