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
    analysed = iter(store.analysed_ids())
    rows = []
    for i, values in enumerate(per_region):
        total, analysable, *provided = values
        ids = set(provided[0]) if provided else set()
        while len(ids) < analysable:
            ids.add(next(analysed, f"pending-{i}-{len(ids)}"))
        rows.append(([(f"tenant-{i}", f"user-{i}")], total, total, analysable, ids))
    monkeypatch.setattr(dashboard, "_map_regions", lambda labels, worker: rows)
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


def test_overview_reports_immediate_attention_breakdown(monkeypatch):
    store = CommonStore()
    _seed(store, 2)
    records = store.list()
    records[0].signals.immediate_attention = True
    records[0].signals.guardrail_bypass = True
    records[0].signals.attention_reasons = ["guardrail_bypass", "high_frustration"]
    records[1].signals.immediate_attention = True
    records[1].signals.kb_issue = True
    records[1].signals.attention_reasons = ["rate_limit"]

    out = _overview_with(monkeypatch, store, [(2, 2)])

    assert out["immediate_attention"] == 2
    assert out["guardrail_bypasses"] == 1
    assert out["kb_issues"] == 1
    assert out["attention_reasons"] == {
        "guardrail_bypass": 1,
        "high_frustration": 1,
        "rate_limit": 1,
    }


def test_prod_backlog_excludes_conversations_outside_analysis_window(monkeypatch):
    from types import SimpleNamespace

    store = CommonStore()
    source_ids = {f"recent-{index}" for index in range(90)}
    monkeypatch.setattr(dashboard, "settings", SimpleNamespace(analysis_lookback_days=lambda env: 15 if env == "prod" else None))
    monkeypatch.setattr(
        dashboard,
        "_map_regions",
        lambda labels, worker: [([("tenant", "user")], 1000, 100, 90, source_ids)],
    )

    out = dashboard.overview(store, env="prod")

    assert out["conversations"] == 1000
    assert out["analysis_population"] == 100
    assert out["outside_analysis_window"] == 900
    assert out["analysis_window_days"] == 15
    assert out["analysable"] == 90
    assert out["empty_transcripts"] == 10
    assert out["unanalysed_pending"] == 90


def test_stale_analyses_do_not_hide_current_pending_conversations(monkeypatch):
    store = CommonStore()
    _seed(store, 6)
    current_ids = {conv.id for conv in CONVERSATIONS[:4]} | {"pending-current"}

    out = _overview_with(monkeypatch, store, [(5, 5, current_ids)])

    assert out["analysed"] == 6
    assert out["unanalysed_pending"] == 1
    assert out["unanalysed"] == 1
