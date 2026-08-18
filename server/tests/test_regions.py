"""Multi-region: region tag flows source → record → reporting; config parses REGIONS."""

from types import SimpleNamespace

from app import config
from app.deidentify import deidentify
from app.domain.analyze import analyze
from app.domain.models import Conversation, Feedback, Message
from app.reporting import operational_stats, product_report
from app.store import CommonStore


def _conv(cid: str, region: str, tenant: str, replied: bool) -> Conversation:
    msgs = [Message(id=f"{cid}-u", role="user", content="help", sequence_num=1, created_at="2020-01-01T00:00:00")]
    if replied:
        msgs.append(Message(id=f"{cid}-a", role="assistant", content="done", sequence_num=2, created_at="2020-01-01T00:00:00"))
    return Conversation(
        id=cid, tenant_id=tenant, title=None, created_at="2020-01-01T00:00:00",
        feedback=Feedback(), region=region, messages=msgs,
    )


def test_region_and_tenant_flow_into_record():
    rec = analyze(_conv("c1", "us", "42", replied=True), "run")
    assert rec.region == "us" and rec.tenant_id == "42"


def test_config_parses_multi_region(monkeypatch):
    monkeypatch.setenv("REGIONS", "us,uk")
    monkeypatch.setenv("REGION_US_CHAT_DB_URL", "postgresql+psycopg://u:p@us-host:5432/d")
    monkeypatch.setenv("REGION_UK_CHAT_DB_URL", "postgresql+psycopg://u:p@uk-host:5432/d")
    regions = config.settings.regions()
    assert {r.label for r in regions} == {"us", "uk"}
    assert next(r for r in regions if r.label == "us").url.endswith("us-host:5432/d")


def test_report_breaks_down_by_region_and_tenant():
    store = CommonStore()
    # us tenant 1: two abandoned (issues); uk tenant 2: one resolved
    for cid, reg, tid, replied in [("a", "us", "1", False), ("b", "us", "1", False), ("c", "uk", "2", True)]:
        conv = _conv(cid, reg, tid, replied)
        store.upsert(analyze(conv, "run"), deidentify(conv))

    ops = operational_stats(store)
    assert ops["by_region"] == {"us": 2, "uk": 1}

    rep = product_report(store)
    assert rep["by_region"]["us"]["issues"] == 2
    assert rep["top_tenants_by_issues"][0] == {"tenant_id": "1", "region": "us", "issues": 2}


def test_store_region_filter_is_strict():
    store = CommonStore()
    for cid, reg in [("x", "us"), ("y", "uk")]:
        conv = _conv(cid, reg, "1", replied=True)
        store.upsert(analyze(conv, "run"), deidentify(conv))
    assert {r.conversation_id for r in store.list(region="us")} == {"x"}
    assert {r.conversation_id for r in store.list(region="uk")} == {"y"}
    assert sum(store.count_by_category(region="us").values()) == 1
    # no region → everything (no loss)
    assert {r.conversation_id for r in store.list()} == {"x", "y"}


def test_platform_threads_map_to_conversations():
    from app.chatdb import _load_platform_region

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self

        def all(self):
            return self.rows

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, _params):
            if "thread_messages" in str(statement):
                return Result([{
                    "id": "m1", "thread_id": "t1", "role": "assistant", "content": "done",
                    "model": "gemini", "tokens": 10, "latency_ms": 25.0,
                    "created_at": "2026-08-11 10:01:00", "sequence_num": 1,
                }])
            return Result([{
                "id": "t1", "tenant_id": "tenant-1", "user_id": "user-1", "title": "Help",
                "created_at": "2026-08-11 10:00:00",
            }])

    class Engine:
        def connect(self):
            return Connection()

    region = config.RegionConfig("eu", "postgresql://example", "chat", "platform")
    conversations = _load_platform_region(region, 10, Engine())
    assert len(conversations) == 1
    assert conversations[0].id == "t1" and conversations[0].region == "eu"
    assert conversations[0].tenant_id == "tenant-1"
    assert conversations[0].messages[0].content == "done"
    assert conversations[0].feedback.rating is None


def test_dashboard_timestamps_are_iso_formatted():
    from app.dashboard import _timestamp

    assert _timestamp("2026-08-13 18:52:59") == "2026-08-13T18:52:59"


def test_dashboard_reuses_region_engine(monkeypatch):
    from app import dashboard

    class FakeEngine:
        def connect(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    engines = []
    monkeypatch.setattr(
        dashboard,
        "resolve_region",
        lambda _region: SimpleNamespace(url="postgresql://example", db_name="chat", schema="chat"),
    )
    monkeypatch.setattr(
        dashboard,
        "_engine_for",
        lambda _url, _db_name: engines.append(FakeEngine()) or engines[-1],
    )
    dashboard._dashboard_engine.cache_clear()
    try:
        with dashboard._connect("us"):
            pass
        with dashboard._connect("us"):
            pass
        assert len(engines) == 1
    finally:
        dashboard._dashboard_engine.cache_clear()


def test_api_rejects_unknown_region_and_lists_regions():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/analysis/regions").status_code == 200
    # unknown region label → 400 (strict; prevents cross-region leakage)
    assert client.get("/api/analysis/conversations", params={"region": "atlantis"}).status_code == 400
