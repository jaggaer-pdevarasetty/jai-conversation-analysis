"""Orchestrator profile: distilled scope + tenant rules, with secrets/URLs excluded (ADR-0018)."""

import json
from pathlib import Path

from app import orchestrator_profile as op


def _make_src(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    (src / "graphs" / "prompts" / "tenants").mkdir(parents=True)
    (src / "config").mkdir(parents=True)
    (src / "graphs" / "prompts" / "rag_system_no_context.txt").write_text("No retrieved documents.")
    # settings.py: safe knobs + a secret that must NOT leak
    (src / "config" / "settings.py").write_text(
        'rag_llm_model: str = "gemini-3-preview"\n'
        "retrieval_top_k: int = 15\n"
        'db_password: str = "SUPER_SECRET_PW"\n'
        'gcc_rag_service_url: str = "https://internal.example/secret"\n'
    )
    (src / "graphs" / "prompts" / "tenants" / "20020000808.json").write_text(json.dumps({
        "platform_name": "ShopBlue",
        "support_contact": "help desk ( https://ubuffalo.example/portal )",
        "prompt_rules": "Refer to the platform as ShopBlue. Do NOT mention eReq — it is outdated. "
                        "Email us at help@buffalo.edu.",
    }))
    return src


def test_profile_has_scope_tools_and_safe_settings(tmp_path, monkeypatch):
    src = _make_src(tmp_path)
    monkeypatch.setattr(op, "_src", lambda: src)
    op.profile.cache_clear()
    prof = op.profile()
    assert "procurement" in prof.lower() and "rag" in prof.lower()  # scope + tools
    assert "rag_llm_model=" in prof and "retrieval_top_k=" in prof  # safe settings
    assert "SUPER_SECRET_PW" not in prof and "internal.example" not in prof  # secrets excluded


def test_tenant_rules_included_but_urls_and_emails_stripped(tmp_path, monkeypatch):
    src = _make_src(tmp_path)
    monkeypatch.setattr(op, "_src", lambda: src)
    op.tenant_rules.cache_clear()
    rules = op.tenant_rules("20020000808")
    assert "ShopBlue" in rules and "eReq" in rules  # the scope rule that fixes the eReq case
    assert "https://" not in rules and "help@buffalo.edu" not in rules  # url/email stripped


def test_missing_source_falls_back(monkeypatch):
    monkeypatch.setattr(op, "_src", lambda: None)
    op.profile.cache_clear()
    op.tenant_rules.cache_clear()
    assert "procurement" in op.profile().lower()  # built-in fallback still describes scope
    assert op.tenant_rules("20020000808") == ""     # no source → no tenant rules
