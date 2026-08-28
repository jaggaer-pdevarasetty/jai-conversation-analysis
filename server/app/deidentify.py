"""De-identification boundary (ADR-0007).

Nothing tenant- or user-identifying may cross into the common area. This module takes a
tenant-scoped source `Conversation` and returns a `CommonConversation` that is keyed by
conversation_id only, with PII scrubbed from all free text. tenant_id / user identifiers
are simply not carried across.
"""

from __future__ import annotations

from dataclasses import replace

from .domain.models import CommonConversation, Conversation, Feedback
from .pii import redact as scrub_pii


def _scrub_feedback(f: Feedback) -> Feedback:
    return Feedback(
        rating=f.rating,
        comment=scrub_pii(f.comment) if f.comment else None,
        message_id=f.message_id,
    )


def deidentify(conv: Conversation) -> CommonConversation:
    messages = [replace(m, content=scrub_pii(m.content)) for m in conv.messages]
    return CommonConversation(
        conversation_id=conv.id,
        messages=messages,
        feedback=_scrub_feedback(conv.feedback),  # primary (back-compat)
        feedbacks=[_scrub_feedback(f) for f in conv.feedbacks],  # ALL feedback (ADR-0022)
        environment=conv.environment,
    )
