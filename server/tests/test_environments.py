"""Environment (uit/prod) isolation + config (ADR-0020)."""

from dataclasses import replace

from app.config import settings, valid_env
from app.deidentify import deidentify
from app.domain.analyze import analyze
from app.fixtures import CONVERSATIONS
from app.store import CommonStore


def test_valid_env_normalises():
    assert valid_env("prod") == "prod"
    assert valid_env("uit") == "uit"
    assert valid_env("nonsense") == "uit"
    assert valid_env(None) == "uit"


def test_langsmith_project_defaults_per_env():
    # tests run with DOTENV_DISABLE=1 → no overrides, so the <env>_<region> convention applies
    assert settings.langsmith_project_for("us", "uit") == "uit_us"
    assert settings.langsmith_project_for("us", "prod") == "prod_us"


def test_store_isolates_environments():
    store = CommonStore()
    conv = CONVERSATIONS[0]

    rec_uit = analyze(conv, "run")
    rec_uit.environment = "uit"
    rec_prod = analyze(conv, "run")
    rec_prod.environment = "prod"
    rec_prod.model_category = "out_of_scope"  # a different label to prove isolation
    cc = deidentify(conv)

    store.upsert(rec_uit, replace(cc, environment="uit"))
    store.upsert(rec_prod, replace(cc, environment="prod"))

    # same conversation id, two environments → two independent records
    assert store.get_analysis(conv.id, "uit").category == "resolved"
    assert store.get_analysis(conv.id, "prod").category == "out_of_scope"
    assert len(store.list(env="uit")) == 1
    assert len(store.list(env="prod")) == 1
    assert store.analysed_ids("uit") == {conv.id}
    assert store.analysed_ids("prod") == {conv.id}
    assert store.is_analysed(conv.id, "uit") and store.is_analysed(conv.id, "prod")
    # a lookup in the wrong env never returns the other's data
    assert store.count_by_category(env="uit")["resolved"] == 1
    assert store.count_by_category(env="uit")["out_of_scope"] == 0
    assert store.count_by_category(env="prod")["out_of_scope"] == 1
