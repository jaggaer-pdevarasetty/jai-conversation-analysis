"""De-identification boundary (ADR-0007).

Nothing tenant- or user-identifying may cross into the common area. This module takes a
tenant-scoped source `Conversation` and returns a `CommonConversation` that is keyed by
conversation_id only, with PII scrubbed from all free text. tenant_id / user identifiers
are simply not carried across.
"""

from __future__ import annotations

from dataclasses import replace

from .domain.models import CommonConversation, Conversation, Feedback
from .domain.signals import scrub_pii


def deidentify(conv: Conversation) -> CommonConversation:
    messages = [replace(m, content=scrub_pii(m.content)) for m in conv.messages]
    feedback = Feedback(
        rating=conv.feedback.rating,
        comment=scrub_pii(conv.feedback.comment) if conv.feedback.comment else None,
    )
    return CommonConversation(conversation_id=conv.id, messages=messages, feedback=feedback)
