from datetime import datetime, timedelta, timezone

from app.domain.models import Conversation, Feedback, Message
from app.fixtures import CONVERSATIONS
from app.run import is_eligible, run_analysis
from app.store import CommonStore


def _conv_at(minutes_ago: int) -> Conversation:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return Conversation(
        id=f"c-{minutes_ago}",
        tenant_id="t",
        title=None,
        created_at=ts,
        feedback=Feedback(),
        messages=[Message(id="m", role="user", content="hi", sequence_num=1, created_at=ts)],
    )


def test_eligibility_requires_5min_inactivity():
    now = datetime.now(timezone.utc)
    assert is_eligible(_conv_at(6), now) is True
    assert is_eligible(_conv_at(1), now) is False  # AC-11


def test_run_analyses_all_eligible_fixtures():
    store = CommonStore()
    summary = run_analysis(store, CONVERSATIONS, now=datetime.now(timezone.utc))
    assert summary.analysed == len(CONVERSATIONS)
    assert summary.failed == 0
    assert store.unanalysed_count() == 0


def test_recently_active_conversation_is_skipped_this_run():
    store = CommonStore()
    summary = run_analysis(store, [_conv_at(2)], now=datetime.now(timezone.utc))
    assert summary.skipped == 1 and summary.analysed == 0


def test_failed_analysis_is_queued_and_retried_next_run():
    store = CommonStore()
    now = datetime.now(timezone.utc)

    def boom(conv, run_id, ts):
        raise RuntimeError("model unavailable")

    first = run_analysis(store, CONVERSATIONS, now=now, classify=boom)
    assert first.failed == len(CONVERSATIONS)
    assert store.unanalysed_count() == len(CONVERSATIONS)  # AC-9 visible

    second = run_analysis(store, CONVERSATIONS, now=now)  # default analyzer succeeds
    assert second.analysed == len(CONVERSATIONS)
    assert store.unanalysed_count() == 0
