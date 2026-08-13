"""Multi-region: region tag flows source → record → reporting; config parses REGIONS."""

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
