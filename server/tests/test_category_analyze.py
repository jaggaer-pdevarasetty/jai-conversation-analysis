from app.domain.analyze import analyze
from app.domain.category import derive_category, recommended_next_step
from app.domain.models import CATEGORIES, Signals
from app.fixtures import CONVERSATIONS


def _sig(**kw):
    base = dict(
        feedback=None,
        repeated_prompts=False,
        abandoned=False,
        error=False,
        out_of_scope_intent=False,
        frustrated=False,
    )
    base.update(kw)
    return Signals(**base)


def test_derive_category_precedence():
    assert derive_category(_sig(feedback="negative", frustrated=True)) == "negative_feedback"
    assert derive_category(_sig(feedback="positive")) == "positive_feedback"
    assert derive_category(_sig(out_of_scope_intent=True)) == "out_of_scope"
    assert derive_category(_sig(repeated_prompts=True)) == "failed_to_resolve"
    assert derive_category(_sig(abandoned=True)) == "failed_to_resolve"
    assert derive_category(_sig()) == "resolved"


def test_next_step_for_every_category():
    for c in CATEGORIES:
        assert recommended_next_step(c)


def test_analyze_covers_all_five_categories_over_fixtures():
    cats = {analyze(c, "run", "2026-08-11T00:00:00Z").category for c in CONVERSATIONS}
    assert cats == set(CATEGORIES)


def test_analyze_high_confidence_on_explicit_feedback():
    with_fb = next(c for c in CONVERSATIONS if c.feedback.rating is not None)
    assert analyze(with_fb, "run").confidence == "high"


def test_analyze_keeps_tenant_and_region_for_analytics():
    # Tenant is a company (not a person) → kept for analytics; content PII is scrubbed separately.
    conv = CONVERSATIONS[0]
    rec = analyze(conv, "run")
    assert rec.tenant_id == conv.tenant_id
    assert hasattr(rec, "region")
    assert rec.category == rec.model_category  # no override yet
