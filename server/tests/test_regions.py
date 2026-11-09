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


def test_prod_eligibility_sql_applies_lookback(monkeypatch):
    from app import chatdb

    captured = {}

    class Result:
        def all(self):
            return [("recent",)]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params or {}
            return Result()

    class Engine:
        def connect(self):
            return Connection()

    monkeypatch.setattr(chatdb, "_platform_layout", lambda _connection, _schema: False)
    region = config.RegionConfig("us", "postgresql://example", "chat", "public")

    ids = chatdb._eligible_in_region(region, Engine(), None, lookback_days=15)

    assert ids == ["recent"]
    assert "last_message_at >= now() - (:lookback_days * interval '1 day')" in captured["sql"]
    assert captured["params"]["lookback_days"] == 15


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


def test_tenant_and_user_rows_include_all_source_regions(monkeypatch):
    from app import dashboard

    tenant_row = {"tenant_id": "42", "name": "Acme", "conversations": 2, "users": 1}
    monkeypatch.setattr(
        dashboard,
        "_map_regions",
        lambda labels, worker: [("us", [tenant_row]), ("eu", [tenant_row])],
    )
    tenant = dashboard.tenants()[0]
    assert tenant["regions"] == ["eu", "us"]
    assert tenant["conversations"] == 4

    user_row = {"user_id": "7", "user_name": "Reviewer", "role": "buyer", "conversations": 3}
    monkeypatch.setattr(
        dashboard,
        "_map_regions",
        lambda labels, worker: [("us", [user_row]), ("uk", [user_row])],
    )
    user = dashboard.users("42")[0]
    assert user["regions"] == ["uk", "us"]
    assert user["conversations"] == 6

    conversation_row = {
        "id": "c1", "title": "Help", "message_count": 2,
        "last_message_at": "2026-10-01T10:00:00+00:00",
    }
    monkeypatch.setattr(
        dashboard,
        "_map_regions",
        lambda labels, worker: [("eu", 1, [conversation_row])],
    )
    conversations, total = dashboard.user_conversations(CommonStore(), "42", "7")
    assert total == 1
    assert conversations[0]["region"] == "eu"


def test_dashboard_telemetry_uses_all_records(monkeypatch):
    from app import dashboard

    store = CommonStore()
    complete = _conv("complete", "us", "1", replied=True)
    complete.messages[-1].ttft_ms = 100
    complete.messages[-1].input_tokens = 10
    complete.messages[-1].output_tokens = 5
    incomplete = _conv("incomplete", "us", "1", replied=True)
    store.upsert(analyze(complete, "run"), deidentify(complete))
    store.upsert(analyze(incomplete, "run"), deidentify(incomplete))
    monkeypatch.setattr(dashboard, "_scan_labels", lambda region, env="uit": [])

    result = dashboard.overview(store, "us")
    assert result["telemetry_complete"] == 1
    assert result["telemetry_total"] == 2


def test_chatdb_timestamps_are_iso_utc():
    from datetime import datetime

    from app.chatdb import utc_timestamp

    assert utc_timestamp(datetime(2026, 8, 13, 18, 52, 59)) == "2026-08-13T18:52:59+00:00"


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
        lambda _region, _env="uit": SimpleNamespace(url="postgresql://example", db_name="chat", schema="chat"),
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
