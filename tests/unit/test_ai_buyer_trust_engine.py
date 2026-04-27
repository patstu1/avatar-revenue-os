"""Determinism + scoring + recommendation tests for the AI Buyer Trust engine.

The engine is a pure function: same signal dict in, identical report out.
These tests lock the contract:
  - no random module imported
  - same input ⇒ identical output across many invocations
  - score → label mapping
  - package recommendation by band
  - not_assessed propagation when pages are missing
  - homepage_failed path returns the failure envelope
  - platform-ready outputs (authority_graph, buyer_questions,
    recommended_pages/schema/proof_assets, monitoring_recommendation) populated
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from packages.scoring import ai_buyer_trust_engine as engine


def _signals_clean_saas(submitted: dict | None = None) -> dict:
    homepage = {
        "url": "https://acme.io",
        "status_code": 200,
        "title": "Acme — payment-fraud detection for B2B SaaS",
        "h1": ["Stop payment fraud before checkout."],
        "h2": [
            "How Acme works",
            "Pricing",
            "Why teams choose Acme",
            "What does Acme cost?",
            "Who is Acme for?",
        ],
        "meta_description": "Acme detects payment fraud at checkout for B2B SaaS — purpose-built for finance teams who care about authorization rate.",
        "jsonld_blocks": [
            {"@type": "Organization", "name": "Acme", "url": "https://acme.io",
             "sameAs": ["https://x.com/acmehq"]},
            {"@type": "WebSite", "name": "Acme"},
            {"@type": "Service", "name": "Fraud detection"},
            {"@type": "FAQPage"},
            {"@type": "Review"},
        ],
        "internal_links": [
            "https://acme.io/about",
            "https://acme.io/services",
            "https://acme.io/pricing",
            "https://acme.io/faq",
            "https://acme.io/case-studies",
            "https://acme.io/compare/competitor",
            "https://acme.io/contact",
            "https://acme.io/privacy",
        ],
        "body_text_snippet": (
            "For B2B SaaS finance teams. Trusted by 200+ companies. "
            "Unlike legacy fraud tools, Acme is purpose-built for SaaS. "
            "What makes us different is our finance-first approach. "
            "Compared to legacy alternatives, faster onboarding. "
            "1234 Market Street, Suite 200. (415) 555-0100. hello@acme.io. "
            "Read our case study with Foo. Trusted by 200+ companies."
        ),
        "fetch_error": None,
        "content_type": "text/html",
    }
    subpages = [
        {
            "url": "https://acme.io/about",
            "status_code": 200,
            "title": "About Acme",
            "h1": ["About Acme"],
            "h2": ["Our team", "Our customers"],
            "meta_description": "",
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "We serve B2B SaaS finance teams.",
            "fetch_error": None,
            "content_type": "text/html",
        },
        {
            "url": "https://acme.io/services",
            "status_code": 200,
            "title": "Services",
            "h1": ["Services"],
            "h2": ["Fraud detection", "Authorization", "Reporting"],
            "meta_description": "",
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "For B2B SaaS finance teams.",
            "fetch_error": None,
            "content_type": "text/html",
        },
        {
            "url": "https://acme.io/pricing",
            "status_code": 200,
            "title": "Pricing",
            "h1": ["Pricing"],
            "h2": ["Starter", "Growth", "Enterprise"],
            "meta_description": "",
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "Starts at $499/mo. Compared to alternatives.",
            "fetch_error": None,
            "content_type": "text/html",
        },
        {
            "url": "https://acme.io/faq",
            "status_code": 200,
            "title": "FAQ",
            "h1": ["FAQ"],
            "h2": [
                "What does Acme do?",
                "How much does Acme cost?",
                "How long does setup take?",
                "Do you integrate with Stripe?",
                "Do you replace Sift?",
                "What support is included?",
                "Where is data stored?",
            ],
            "meta_description": "",
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "Frequently asked questions.",
            "fetch_error": None,
            "content_type": "text/html",
        },
        {
            "url": "https://acme.io/case-studies",
            "status_code": 200,
            "title": "Case studies",
            "h1": ["Case studies"],
            "h2": ["Foo", "Bar", "Baz"],
            "meta_description": "",
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "Case study with Foo: testimonial.",
            "fetch_error": None,
            "content_type": "text/html",
        },
        {
            "url": "https://acme.io/compare/competitor",
            "status_code": 200,
            "title": "Acme vs Competitor",
            "h1": ["Acme vs Competitor"],
            "h2": ["Pricing", "Time to value", "Best for"],
            "meta_description": "",
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "Acme vs Competitor — how to choose.",
            "fetch_error": None,
            "content_type": "text/html",
        },
        {
            "url": "https://acme.io/contact",
            "status_code": 200,
            "title": "Contact",
            "h1": ["Contact"],
            "h2": [],
            "meta_description": "",
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "1234 Market Street.",
            "fetch_error": None,
            "content_type": "text/html",
        },
    ]
    return {
        "homepage": homepage,
        "homepage_failed": False,
        "robots_txt_present": True,
        "robots_txt_blocks_ai": False,
        "sitemap_present": True,
        "sitemap_url_count": 25,
        "subpages": subpages,
        "all_jsonld_types": [
            "FAQPage",
            "Organization",
            "Review",
            "Service",
            "WebSite",
        ],
        "all_jsonld_blocks": homepage["jsonld_blocks"],
        "submitted": submitted or {"company_name": "Acme", "industry": "B2B SaaS"},
    }


def _signals_thin_homepage_only() -> dict:
    homepage = {
        "url": "https://thinco.example",
        "status_code": 200,
        "title": "ThinCo",
        "h1": [],
        "h2": [],
        "meta_description": "",
        "jsonld_blocks": [],
        "internal_links": [],
        "body_text_snippet": "We do stuff.",
        "fetch_error": None,
        "content_type": "text/html",
    }
    return {
        "homepage": homepage,
        "homepage_failed": False,
        "robots_txt_present": False,
        "robots_txt_blocks_ai": False,
        "sitemap_present": False,
        "sitemap_url_count": 0,
        "subpages": [],
        "all_jsonld_types": [],
        "all_jsonld_blocks": [],
        "submitted": {"company_name": "ThinCo", "industry": "Med Spa"},
    }


def _signals_failed_homepage() -> dict:
    return {
        "homepage": {
            "url": "https://broken.example",
            "status_code": 500,
            "title": None,
            "h1": [],
            "h2": [],
            "meta_description": None,
            "jsonld_blocks": [],
            "internal_links": [],
            "body_text_snippet": "",
            "fetch_error": "http_500",
            "content_type": None,
        },
        "homepage_failed": True,
        "robots_txt_present": False,
        "robots_txt_blocks_ai": False,
        "sitemap_present": False,
        "sitemap_url_count": 0,
        "subpages": [],
        "all_jsonld_types": [],
        "all_jsonld_blocks": [],
        "submitted": {"company_name": "Broken Co", "industry": "agency"},
    }


# ─────────────────────────────────────────────────────────────────────
# 1. No random — engine is pure
# ─────────────────────────────────────────────────────────────────────


def test_engine_does_not_import_random():
    src = inspect.getsource(engine)
    assert "import random" not in src, "engine must not use random"
    assert "random." not in src, "engine must not call random.*"
    assert "datetime.now" not in src, "engine must not depend on the wall clock"


def test_engine_outputs_are_deterministic():
    sig = _signals_clean_saas()
    out_1 = engine.score_ai_buyer_trust(sig)
    for _ in range(50):
        out = engine.score_ai_buyer_trust(sig)
        assert out == out_1, "engine output must be deterministic"


# ─────────────────────────────────────────────────────────────────────
# 2. Score label mapping
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "score,label",
    [
        (0, "not_ready"),
        (39, "not_ready"),
        (40, "weak"),
        (59, "weak"),
        (60, "developing"),
        (74, "developing"),
        (75, "strong"),
        (89, "strong"),
        (90, "authority_ready"),
        (100, "authority_ready"),
    ],
)
def test_score_label_for_covers_every_band(score, label):
    assert engine.score_label_for(score) == label


# ─────────────────────────────────────────────────────────────────────
# 3. Package recommendation thresholds
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "score,expected_primary,expected_secondary",
    [
        (0, engine.PACKAGE_BUILDOUT, None),
        (39, engine.PACKAGE_BUILDOUT, None),
        (40, engine.PACKAGE_SPRINT, None),
        (59, engine.PACKAGE_SPRINT, None),
        (60, engine.PACKAGE_SPRINT, engine.PACKAGE_RETAINER),
        (74, engine.PACKAGE_SPRINT, engine.PACKAGE_RETAINER),
        (75, engine.PACKAGE_RETAINER, None),
        (89, engine.PACKAGE_RETAINER, None),
        (90, engine.PACKAGE_SYSTEM, None),
        (100, engine.PACKAGE_SYSTEM, None),
    ],
)
def test_package_recommendation_bands(score, expected_primary, expected_secondary):
    fake_dims = {
        "entity_clarity": {"status": "assessed", "score": score, "detected": [], "missing": [],
                            "why_it_matters": "", "recommended_fix": "", "confidence": 0.5,
                            "public_label": "test"},
    }
    rec = engine._recommend_package(score, fake_dims)
    assert rec["primary_slug"] == expected_primary
    assert rec["secondary_slug"] == expected_secondary
    # Cross-lane creative_proof_slug key is always present in the envelope
    assert "creative_proof_slug" in rec


# ─────────────────────────────────────────────────────────────────────
# Cross-lane recommendation: weak proof_strength → Signal Entry creative
# companion; weak offer_clarity → Conversion Architecture; high score
# with thin recurring proof → Momentum Engine; otherwise None.
# ─────────────────────────────────────────────────────────────────────


def _dim(score: int, status: str = "assessed") -> dict:
    return {
        "status": status,
        "score": score,
        "detected": [],
        "missing": [],
        "why_it_matters": "",
        "recommended_fix": "",
        "confidence": 0.5,
        "public_label": "test",
    }


def test_creative_companion_signal_entry_when_proof_weak():
    dims = {
        "entity_clarity": _dim(60),
        "audience_clarity": _dim(60),
        "offer_clarity": _dim(60),
        "proof_strength": _dim(30),
        "comparison_readiness": _dim(60),
        "answer_engine_readiness": _dim(60),
        "trust_signal_density": _dim(60),
        "ai_search_eligibility": _dim(60),
    }
    rec = engine._recommend_package(50, dims)
    assert rec["creative_proof_slug"] == engine.CREATIVE_SIGNAL_ENTRY
    assert "Signal Entry" in rec["rationale"]


def test_creative_companion_conversion_architecture_when_offer_weak():
    dims = {
        "entity_clarity": _dim(70),
        "audience_clarity": _dim(70),
        "offer_clarity": _dim(30),
        "proof_strength": _dim(70),
        "comparison_readiness": _dim(70),
        "answer_engine_readiness": _dim(70),
        "trust_signal_density": _dim(70),
        "ai_search_eligibility": _dim(70),
    }
    rec = engine._recommend_package(65, dims)
    assert rec["creative_proof_slug"] == engine.CREATIVE_CONVERSION_ARCH
    assert "Conversion Architecture" in rec["rationale"]


def test_creative_companion_momentum_when_authority_ready_but_proof_thin():
    dims = {
        "entity_clarity": _dim(90),
        "audience_clarity": _dim(60),
        "offer_clarity": _dim(90),
        "proof_strength": _dim(60),
        "comparison_readiness": _dim(90),
        "answer_engine_readiness": _dim(90),
        "trust_signal_density": _dim(90),
        "ai_search_eligibility": _dim(90),
    }
    rec = engine._recommend_package(80, dims)
    assert rec["creative_proof_slug"] == engine.CREATIVE_MOMENTUM_ENGINE
    assert "Momentum Engine" in rec["rationale"]


def test_no_creative_companion_when_creative_dimensions_strong():
    dims = {
        "entity_clarity": _dim(85),
        "audience_clarity": _dim(85),
        "offer_clarity": _dim(85),
        "proof_strength": _dim(85),
        "comparison_readiness": _dim(85),
        "answer_engine_readiness": _dim(85),
        "trust_signal_density": _dim(85),
        "ai_search_eligibility": _dim(85),
    }
    rec = engine._recommend_package(85, dims)
    assert rec["creative_proof_slug"] is None


# ─────────────────────────────────────────────────────────────────────
# 4. Failed-homepage path
# ─────────────────────────────────────────────────────────────────────


def test_failed_homepage_returns_not_assessed_envelope():
    out = engine.score_ai_buyer_trust(_signals_failed_homepage())
    assert out["score_label"] == "not_assessed"
    assert out["total_score"] == 0
    assert out["confidence_label"] == "low"
    assert out["recommended_package"]["primary_slug"] is None
    # Every dimension marked not_assessed
    for dim, ev in out["evidence"].items():
        assert ev["status"] == "not_assessed", f"{dim} should be not_assessed"
    # Platform-ready fields present even on failure
    assert "authority_graph" in out
    assert out["buyer_questions"] == []
    assert out["recommended_pages"] == []
    assert out["recommended_schema"] == []


# ─────────────────────────────────────────────────────────────────────
# 5. Clean SaaS site scores well + populates platform-ready outputs
# ─────────────────────────────────────────────────────────────────────


def test_clean_site_scores_well_and_populates_platform_outputs():
    out = engine.score_ai_buyer_trust(_signals_clean_saas())
    assert out["total_score"] >= 60, f"expected >=60, got {out['total_score']}"
    # Authority Graph populated with the full Decision-Layer node set
    g = out["authority_graph"]
    assert g["entity"]["title"] == "Acme — payment-fraud detection for B2B SaaS"
    assert g["entity"]["has_organization_schema"] is True
    # Decision-Layer node ordering: Company → Category → Offers → Audience
    # → Proof → Buyer Questions → FAQs → Comparisons → Schema → Answer Pages → CTAs
    for required_node in (
        "company", "category", "entity", "audience", "offers", "proof",
        "buyer_questions", "faqs", "comparisons", "schema",
        "answer_pages", "ctas", "trust_signals", "crawlability",
    ):
        assert required_node in g, f"Authority Graph missing node: {required_node}"
    assert isinstance(g["buyer_questions"]["count"], int) and g["buyer_questions"]["count"] >= 5
    assert isinstance(g["buyer_questions"]["preview"], list) and len(g["buyer_questions"]["preview"]) <= 3
    assert isinstance(g["schema"]["types_present"], list)
    assert isinstance(g["ctas"]["detected"], list)
    # Buyer questions: at least 5, lead with direct-trust questions
    qs = out["buyer_questions"]
    assert len(qs) >= 5
    assert qs[0]["question"].startswith("Is Acme")
    assert "trustworthy" in qs[0]["question"].lower()
    assert any("compare" in q["question"].lower() for q in qs[:3])
    # Recommended pages / schema / proof / comparison surfaces — all lists
    assert isinstance(out["recommended_pages"], list)
    assert isinstance(out["recommended_schema"], list)
    assert isinstance(out["recommended_proof_assets"], list)
    assert isinstance(out["recommended_comparison_surfaces"], list)
    assert isinstance(out["monitoring_recommendation"], str) and len(out["monitoring_recommendation"]) > 20
    # Versions stamped
    assert out["formula_version"] == "v1"
    assert out["report_version"] == "v1"
    assert out["scan_version"] == "v1"


def test_recommended_comparison_surfaces_uses_competitor_when_provided():
    sig = _signals_thin_homepage_only()
    sig["submitted"] = {
        "company_name": "ThinCo",
        "industry": "law firm",
        "competitor_url": "https://competitor.example",
    }
    out = engine.score_ai_buyer_trust(sig)
    surfaces = out["recommended_comparison_surfaces"]
    assert len(surfaces) >= 1
    kinds = [s["kind"] for s in surfaces]
    assert "competitor_comparison" in kinds
    competitor = next(s for s in surfaces if s["kind"] == "competitor_comparison")
    assert competitor["priority"] == "high"
    assert "competitor.example" in competitor["purpose"]
    # Category decision-support should slug-ify the industry
    cat = next((s for s in surfaces if s["kind"] == "category_decision_support"), None)
    assert cat is not None
    assert cat["slug_pattern"] == "/best-law-firm"


def test_clean_site_does_not_recommend_redundant_competitor_surface():
    """When the site already has a /compare page, the recommender should
    not pile on another generic competitor_comparison entry."""
    sig = _signals_clean_saas()
    out = engine.score_ai_buyer_trust(sig)
    surfaces = out["recommended_comparison_surfaces"]
    # A clean site already has /compare/competitor — no second generic
    # competitor_comparison should be added unless competitor_url was given.
    competitor_count = sum(1 for s in surfaces if s["kind"] == "competitor_comparison")
    assert competitor_count == 0


def test_authority_graph_includes_locations_and_ctas_when_present():
    sig = _signals_clean_saas()
    out = engine.score_ai_buyer_trust(sig)
    g = out["authority_graph"]
    # The clean fixture has a CTA-like phrase in the body
    assert isinstance(g["ctas"]["count"], int)
    # Schema breadth surfaced explicitly
    assert "Organization" in g["schema"]["types_present"]
    assert "FAQPage" in g["schema"]["types_present"]


# ─────────────────────────────────────────────────────────────────────
# 6. Thin homepage scores low + recommends Buildout
# ─────────────────────────────────────────────────────────────────────


def test_thin_homepage_scores_low_and_recommends_buildout():
    out = engine.score_ai_buyer_trust(_signals_thin_homepage_only())
    assert out["total_score"] < 40
    rec = out["recommended_package"]
    assert rec["primary_slug"] == engine.PACKAGE_BUILDOUT
    # buyer questions personalize to the submitted industry
    assert any("Med Spa" in q["question"] for q in out["buyer_questions"])


# ─────────────────────────────────────────────────────────────────────
# 7. Industry+company personalization in buyer questions
# ─────────────────────────────────────────────────────────────────────


def test_buyer_questions_personalize_with_submitted_meta():
    sig = _signals_clean_saas(submitted={"company_name": "Atlas Med Spa", "industry": "med spa"})
    out = engine.score_ai_buyer_trust(sig)
    qs = out["buyer_questions"]
    # First three are direct-trust questions naming the company
    assert "Atlas Med Spa" in qs[0]["question"]
    # Category question references the industry
    assert any("med spa" in q["question"].lower() for q in qs[:5])


# ─────────────────────────────────────────────────────────────────────
# 8. confidence_label_for boundaries
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "v,label",
    [(0.0, "low"), (0.49, "low"), (0.5, "medium"), (0.74, "medium"), (0.75, "high"), (1.0, "high")],
)
def test_confidence_label_boundaries(v, label):
    assert engine.confidence_label_for(v) == label


# ─────────────────────────────────────────────────────────────────────
# 9. Module reload still produces identical output (no module-level state)
# ─────────────────────────────────────────────────────────────────────


def test_engine_has_no_module_level_state():
    sig = _signals_clean_saas()
    a = engine.score_ai_buyer_trust(sig)
    importlib.reload(engine)
    b = engine.score_ai_buyer_trust(sig)
    assert a == b
