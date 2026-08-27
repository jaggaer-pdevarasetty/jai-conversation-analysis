"""Early Access customer matching (mirrors the Confluence roster)."""

from app.ea_customers import ea_info


def test_matches_known_ea_customers():
    assert ea_info("ENEL S.p.A.")["label"] == "ENEL"
    assert ea_info("Orano")["product"] == "JA"
    for name in ("Emirates Group", "VISTA", "Bosch GmbH"):
        assert ea_info(name) is not None


def test_enel_is_privacy_sensitive():
    info = ea_info("Enel")
    assert info["privacy_sensitive"] is True
    assert "RoPA" in info["privacy"]


def test_blocked_status_carried_through():
    assert ea_info("Orano")["status"] == "blocked"


def test_non_ea_and_partial_words_do_not_match():
    assert ea_info("Acme Corp") is None
    assert ea_info("Enelson Ltd") is None  # 'enel' is a substring but not a whole word
    assert ea_info(None) is None
    assert ea_info("") is None
