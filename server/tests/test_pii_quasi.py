"""PII + quasi-identifier scrubbing and user pseudonymization (ADR-0018 safety)."""

from app.domain.signals import scrub_pii
from app.pii import pseudonymize


def test_direct_pii_removed():
    out = scrub_pii("email john.doe@acme.com or call +1 555-123-4567; SSN 123-45-6789")
    assert "john.doe@acme.com" not in out and "555-123-4567" not in out and "123-45-6789" not in out
    assert "[email]" in out and "[phone]" in out and "[ssn]" in out


def test_quasi_identifiers_blurred():
    out = scrub_pii("req 12345678, total $3,703.85 on 8/12/2026, code BUF-TAW8, dated Aug 12, 2026")
    for leak in ("12345678", "3,703.85", "8/12/2026", "BUF-TAW8", "Aug 12, 2026"):
        assert leak not in out, f"{leak!r} leaked"
    assert "[amount]" in out and "[date]" in out and "[id]" in out


def test_small_numbers_not_over_redacted():
    # pagination/counts must survive so the topic stays readable
    out = scrub_pii("showing 1-20 of 21 requisitions")
    assert out == "showing 1-20 of 21 requisitions"


def test_pseudonymize_is_stable_and_hides_raw():
    a = pseudonymize("user", "9464669")
    b = pseudonymize("user", "9464669")
    assert a == b  # stable
    assert a and "9464669" not in a and a.startswith("user-")
    assert pseudonymize("user", None) is None
