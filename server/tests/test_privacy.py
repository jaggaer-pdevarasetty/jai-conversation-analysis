"""Privacy modes (admin vs pooled AC-10) + expanded structured-PII redaction."""

from app import privacy
from app.domain.signals import scrub_pii


class _Settings:
    def __init__(self, mode):
        self.privacy_mode = mode


def test_pooled_mode_pseudonymizes_and_drops_identity(monkeypatch):
    monkeypatch.setattr(privacy, "settings", _Settings("pooled"))
    meta = {
        "tenant_id": "20040002086", "tenant_name": "Natwest",
        "user_id": "7", "user_name": "gwiggins@jaggaer.com",
        "title": "Natwest procurement issue", "status": "active",
        # EA badge names the tenant — must NOT survive pooled mode (regression: PR #12 leak).
        "ea": {"label": "Natwest", "product": "JI", "status": "active", "privacy": "", "privacy_sensitive": False},
    }
    out = privacy.apply_meta(meta)
    assert out["tenant_name"].startswith("tenant-") and out["user_name"].startswith("user-")
    assert out["tenant_id"] is None and out["user_id"] is None and out["title"] is None
    assert out["ea"] is None  # EA badge dropped in pooled mode
    blob = str(out)
    assert "Natwest" not in blob and "gwiggins@jaggaer.com" not in blob  # AC-10: no identity


def test_admin_mode_passes_identity_through(monkeypatch):
    monkeypatch.setattr(privacy, "settings", _Settings("admin"))
    assert privacy.apply_meta({"tenant_id": "1", "tenant_name": "Natwest"})["tenant_name"] == "Natwest"


def test_pooled_pseudonyms_are_stable(monkeypatch):
    monkeypatch.setattr(privacy, "settings", _Settings("pooled"))
    a = privacy.apply_meta({"tenant_id": "42", "user_id": "9"})
    b = privacy.apply_meta({"tenant_id": "42", "user_id": "9"})
    assert a["tenant_name"] == b["tenant_name"]  # same tenant → same pseudonym (grouping works)


def test_pii_redacts_ip_iban_and_ssn():
    out = scrub_pii("host 192.168.1.1 iban GB82WEST12345698765432 ssn 123-45-6789")
    assert "192.168.1.1" not in out and "[ip]" in out
    assert "GB82WEST12345698765432" not in out and "[iban]" in out
    assert "123-45-6789" not in out and "[ssn]" in out
