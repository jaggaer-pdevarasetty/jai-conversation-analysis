"""Dashboard overview backlog maths — the ANALYSABLE population (no chat DB needed).

The "waiting for analysis" number must count only conversations that can ever be analysed:
empty-transcript conversations are permanently excluded by the empty-transcript guard, so
including them (total − analysed) made the backlog non-zero forever. Here the per-region
chat-DB scan is stubbed and the arithmetic is verified against a real in-memory store.
"""

from app import dashboard
from app.deidentify import deidentify
from app.domain.analyze import analyze
from app.fixtures import CONVERSATIONS
from app.store import CommonStore


def _overview_with(monkeypatch, store, per_region):
    """Run overview() with the chat-DB scan stubbed: per_region = [(total, analysable), …]."""
    monkeypatch.setattr(
        dashboard,
        "_map_regions",
        lambda labels, worker: [
            ([(f"tenant-{i}", f"user-{i}")], total, analysable)
            for i, (total, analysable) in enumerate(per_region)
        ],
    )
    return dashboard.overview(store)


def _seed(store, n):
    for conv in CONVERSATIONS[:n]:
        store.upsert(analyze(conv, "run"), deidentify(conv))


def test_backlog_excludes_never_analysable_empty_transcripts(monkeypatch):
    store = CommonStore()
    _seed(store, 6)
    store.mark_failed("failed-1", region="us")

    out = _overview_with(monkeypatch, store, [(100, 90), (50, 45)])
    assert out["conversations"] == 150          # all non-deleted source records
    assert out["analysable"] == 135             # only these can ever be analysed
    assert out["empty_transcripts"] == 15       # surfaced separately, never in the backlog
    assert out["analysed"] == 6
    assert out["unanalysed_failed"] == 1
    assert out["unanalysed_pending"] == 135 - 6 - 1  # analysable − analysed − failed
    assert out["unanalysed"] == out["unanalysed_pending"] + 1


def test_backlog_reaches_zero_and_clamps_when_analysed_exceeds_analysable(monkeypatch):
    """Everything analysable analysed → waiting = 0 (not a permanent residue of empties, and
    not negative when analysed rows outlive their deleted/emptied source conversations)."""
    store = CommonStore()
    _seed(store, 6)

    out = _overview_with(monkeypatch, store, [(100, 5)])  # 6 analysed > 5 analysable
    assert out["empty_transcripts"] == 95
    assert out["unanalysed_pending"] == 0  # clamped — no negative backlog
    assert out["unanalysed"] == 0

    clean = _overview_with(monkeypatch, store, [(100, 6)])  # exact match
    assert clean["unanalysed_pending"] == 0 and clean["unanalysed"] == 0
