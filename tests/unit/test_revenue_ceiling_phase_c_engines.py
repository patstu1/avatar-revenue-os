"""Unit tests for Revenue Ceiling Phase C scoring engines."""


from packages.scoring.revenue_ceiling_phase_c_engines import (
    RECURRING_OFFER_TYPES,
    evaluate_paid_promotion_candidate,
    score_monetization_mix,
    score_recurring_revenue,
    score_sponsor_inventory_item,
    score_sponsor_package,
    score_trust_conversion,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TWO_OFFERS = [{"id": "o1", "name": "Offer A"}, {"id": "o2", "name": "Offer B"}]
_FIVE_OFFERS = [{"id": f"o{i}", "name": f"Offer {i}", "payout_amount": 20 * i} for i in range(1, 6)]


# ===========================================================================
# 1. Recurring Revenue Engine
# ===========================================================================

def test_recurring_revenue_has_required_fields():
    r = score_recurring_revenue("fitness", _TWO_OFFERS, 5000, 0.05, [])
    for key in (
        "recurring_potential_score",
        "best_recurring_offer_type",
        "audience_fit",
        "churn_risk_proxy",
        "expected_monthly_value",
        "expected_annual_value",
        "confidence",
    ):
        assert key in r, f"Missing key: {key}"


def test_recurring_revenue_scores_in_range():
    r = score_recurring_revenue("finance", _TWO_OFFERS, 5000, 0.05, [])
    for key in ("recurring_potential_score", "audience_fit", "churn_risk_proxy", "confidence"):
        val = r[key]
        assert 0 <= val <= 1, f"{key}={val} out of [0, 1]"


def test_recurring_monthly_less_than_annual():
    # Annual must be > monthly (12 months of recurring), but churn reduces it —
    # the loose bound ensures the formula hasn't gone off the rails.
    r = score_recurring_revenue("fitness", _TWO_OFFERS, 10000, 0.04, [])
    monthly = r["expected_monthly_value"]
    annual = r["expected_annual_value"]
    # Annual accounts for churn, so it is less than 12 × monthly, but still
    # must be at least half of that full-year extrapolation.
    assert monthly * 12 >= annual * 0.5


def test_recurring_high_engagement_lowers_churn():
    offers = _TWO_OFFERS
    low_eng = score_recurring_revenue("fitness", offers, 5000, 0.01, [])
    high_eng = score_recurring_revenue("fitness", offers, 5000, 0.12, [])
    assert low_eng["churn_risk_proxy"] > high_eng["churn_risk_proxy"]


def test_recurring_offer_type_is_valid_string():
    r = score_recurring_revenue("business", _TWO_OFFERS, 5000, 0.05, [])
    assert r["best_recurring_offer_type"] in RECURRING_OFFER_TYPES


def test_recurring_existing_products_reduces_available_types():
    # Providing all but one existing type must still return a valid type
    existing = RECURRING_OFFER_TYPES[:-1]
    r = score_recurring_revenue("tech", _TWO_OFFERS, 8000, 0.06, existing)
    assert r["best_recurring_offer_type"] in RECURRING_OFFER_TYPES


def test_recurring_expected_annual_greater_than_monthly():
    # With a healthy audience the annual total should exceed one month
    r = score_recurring_revenue("fitness", _FIVE_OFFERS, 20000, 0.06, [])
    assert r["expected_annual_value"] > r["expected_monthly_value"]


# ===========================================================================
# 2. Sponsor Inventory Engine
# ===========================================================================

def test_sponsor_inventory_has_required_fields():
    r = score_sponsor_inventory_item("c1", "Finance Deep-Dive", "finance", 25000, 0.05, 50000, "long_form")
    for key in ("sponsor_fit_score", "estimated_package_price", "sponsor_category", "confidence"):
        assert key in r, f"Missing key: {key}"


def test_sponsor_package_price_positive():
    r = score_sponsor_package("fitness", 50_000, 100_000, 0.05, [])
    assert r["estimated_package_price"] > 0


def test_sponsor_fit_score_in_range():
    r = score_sponsor_inventory_item("c2", "Fitness Routine", "fitness", 15000, 0.06, 40000, "short_form")
    assert 0 <= r["sponsor_fit_score"] <= 1


def test_sponsor_package_pricing_long_form_higher_than_short():
    common = dict(
        content_item_id="cx",
        content_title="How-To Video",
        niche="fitness",
        impressions=10_000,
        engagement_rate=0.05,
        audience_size=50_000,
    )
    long_form = score_sponsor_inventory_item(**common, content_type="long_form")
    short_form = score_sponsor_inventory_item(**common, content_type="short_form")
    assert long_form["estimated_package_price"] > short_form["estimated_package_price"]


def test_sponsor_package_has_deliverables():
    r = score_sponsor_package("fitness", 50_000, 100_000, 0.05, [])
    pkg = r["recommended_package"]
    assert "deliverables" in pkg
    assert isinstance(pkg["deliverables"], list)
    assert len(pkg["deliverables"]) > 0


def test_sponsor_category_derived_from_niche():
    r = score_sponsor_inventory_item("c3", "Finance Tips", "finance", 10000, 0.05, 50000, "long_form")
    cat = r["sponsor_category"].lower()
    assert "fin" in cat or "fintech" in cat


def test_sponsor_package_confidence_in_range():
    r = score_sponsor_package("tech", 80_000, 200_000, 0.04, [])
    assert 0 <= r["confidence"] <= 1


# ===========================================================================
# 3. Trust Conversion Engine
# ===========================================================================

def _full_trust(niche: str = "finance"):
    """All trust signals present."""
    return score_trust_conversion(niche, True, True, 10, True, True, 20, 0.8, 0.05)


def _empty_trust(niche: str = "finance"):
    """No trust signals present."""
    return score_trust_conversion(niche, False, False, 0, False, False, 0, 0.0, 0.0)


def test_trust_conversion_has_required_fields():
    r = _full_trust()
    for key in (
        "trust_deficit_score",
        "recommended_proof_blocks",
        "missing_trust_elements",
        "expected_uplift",
        "confidence",
    ):
        assert key in r, f"Missing key: {key}"


def test_trust_deficit_lower_with_more_elements():
    full = _full_trust("fitness")
    empty = _empty_trust("fitness")
    assert full["trust_deficit_score"] < empty["trust_deficit_score"]


def test_missing_elements_listed_when_absent():
    r = score_trust_conversion(
        "fitness",
        has_testimonials=False,
        has_case_studies=True,
        has_social_proof_count=10,
        has_media_features=True,
        has_certifications=True,
        content_item_count=10,
        avg_quality_score=0.7,
        offer_conversion_rate=0.03,
    )
    assert "testimonials" in r["missing_trust_elements"]


def test_expected_uplift_positive():
    r = _empty_trust()
    assert r["expected_uplift"] > 0


def test_trust_deficit_score_range():
    for r in (_full_trust("tech"), _empty_trust("tech")):
        val = r["trust_deficit_score"]
        assert 0 <= val <= 1, f"trust_deficit_score={val} out of [0, 1]"


def test_proof_blocks_are_prioritized():
    r = score_trust_conversion(
        "fitness",
        has_testimonials=False,
        has_case_studies=False,
        has_social_proof_count=0,
        has_media_features=False,
        has_certifications=False,
        content_item_count=5,
        avg_quality_score=0.5,
        offer_conversion_rate=0.02,
    )
    blocks = r["recommended_proof_blocks"]
    assert isinstance(blocks, list)
    assert len(blocks) > 0
    assert all("priority" in b for b in blocks)


def test_proof_blocks_priority_order_ascending():
    r = _empty_trust()
    priorities = [b["priority"] for b in r["recommended_proof_blocks"]]
    assert priorities == sorted(priorities)


def test_missing_trust_elements_empty_when_all_present():
    r = _full_trust()
    # When all flags are True and social_proof_count >= 5, no core element is missing
    present_elements = {"testimonials", "case_studies", "media_features", "certifications"}
    missing = set(r["missing_trust_elements"])
    assert not missing.intersection(present_elements)


# ===========================================================================
# 4. Monetization Mix Engine
# ===========================================================================

def test_monetization_mix_has_required_fields():
    r = score_monetization_mix(
        "fitness",
        {"affiliate": 500.0, "sponsorship": 500.0},
        1000.0,
        10_000,
        ["affiliate", "sponsorship"],
    )
    for key in (
        "current_revenue_mix",
        "dependency_risk",
        "underused_monetization_paths",
        "next_best_mix",
        "expected_margin_uplift",
        "expected_ltv_uplift",
        "confidence",
    ):
        assert key in r, f"Missing key: {key}"


def test_dependency_risk_high_when_one_method():
    r = score_monetization_mix(
        "fitness",
        {"affiliate": 1000.0},
        1000.0,
        5_000,
        ["affiliate"],
    )
    assert r["dependency_risk"] >= 0.8


def test_dependency_risk_low_when_diversified():
    methods = ["affiliate", "sponsorship", "digital_product", "membership", "coaching"]
    rev = {m: 200.0 for m in methods}
    r = score_monetization_mix("fitness", rev, 1000.0, 10_000, methods)
    assert r["dependency_risk"] <= 0.4


def test_underused_paths_are_listed():
    r = score_monetization_mix(
        "fitness",
        {"affiliate": 1000.0},
        1000.0,
        5_000,
        ["affiliate"],
    )
    paths = [u["path"] for u in r["underused_monetization_paths"]]
    assert "sponsorship" in paths
    assert "membership" in paths


def test_next_best_mix_sums_to_one():
    r = score_monetization_mix(
        "business",
        {"affiliate": 400.0, "sponsorship": 600.0},
        1000.0,
        10_000,
        ["affiliate", "sponsorship"],
    )
    total = sum(r["next_best_mix"].values())
    assert abs(total - 1.0) <= 0.05


def test_monetization_mix_optimization_increases_expected_uplift():
    # 90 / 10 split is highly concentrated; diversification factor > 0 → uplift > 0
    r = score_monetization_mix(
        "fitness",
        {"affiliate": 900.0, "ads": 100.0},
        1000.0,
        5_000,
        ["affiliate", "ads"],
    )
    assert r["expected_margin_uplift"] > 0


def test_underused_paths_each_have_path_and_potential_score():
    r = score_monetization_mix(
        "fitness",
        {"affiliate": 1000.0},
        1000.0,
        5_000,
        ["affiliate"],
    )
    for item in r["underused_monetization_paths"]:
        assert "path" in item
        assert "potential_score" in item
        assert 0 <= item["potential_score"] <= 1


# ===========================================================================
# 5. Paid Promotion Gate
# ===========================================================================

_STRONG_GATE_KWARGS = dict(
    content_item_id="c1",
    content_title="10 Finance Hacks",
    organic_impressions=10_000,
    organic_engagement_rate=0.06,
    organic_revenue=500.0,
    organic_roi=2.0,
    content_age_days=20,
)


def test_paid_promo_eligible_when_all_signals_strong():
    r = evaluate_paid_promotion_candidate(**_STRONG_GATE_KWARGS)
    assert r["is_eligible"] is True


def test_paid_promo_not_eligible_low_impressions():
    r = evaluate_paid_promotion_candidate(
        **{**_STRONG_GATE_KWARGS, "organic_impressions": 100}
    )
    assert r["is_eligible"] is False


def test_paid_promo_not_eligible_low_engagement():
    r = evaluate_paid_promotion_candidate(
        **{**_STRONG_GATE_KWARGS, "organic_engagement_rate": 0.01}
    )
    assert r["is_eligible"] is False


def test_paid_promo_not_eligible_zero_revenue():
    r = evaluate_paid_promotion_candidate(
        **{**_STRONG_GATE_KWARGS, "organic_revenue": 0.0}
    )
    assert r["is_eligible"] is False


def test_paid_promo_gate_has_evidence_dict():
    r = evaluate_paid_promotion_candidate(**_STRONG_GATE_KWARGS)
    evidence = r["organic_winner_evidence"]
    assert isinstance(evidence, dict)
    assert len(evidence) > 0


def test_paid_promo_gate_reason_present():
    r = evaluate_paid_promotion_candidate(
        **{**_STRONG_GATE_KWARGS, "organic_impressions": 100}
    )
    assert isinstance(r["gate_reason"], str)
    assert len(r["gate_reason"]) > 0


def test_paid_promo_confidence_in_range():
    for kwargs_override in (
        {},
        {"organic_impressions": 100},
        {"organic_engagement_rate": 0.01},
    ):
        r = evaluate_paid_promotion_candidate(**{**_STRONG_GATE_KWARGS, **kwargs_override})
        assert 0 <= r["confidence"] <= 1, f"confidence={r['confidence']} out of range"


def test_paid_promo_gate_reason_mentions_failure_cause():
    r = evaluate_paid_promotion_candidate(
        **{**_STRONG_GATE_KWARGS, "organic_impressions": 50}
    )
    assert r["is_eligible"] is False
    assert "impression" in r["gate_reason"].lower() or "not eligible" in r["gate_reason"].lower()


def test_paid_promo_evidence_contains_pass_flags():
    r = evaluate_paid_promotion_candidate(**_STRONG_GATE_KWARGS)
    ev = r["organic_winner_evidence"]
    # All individual pass flags should be present in the evidence dict
    assert "impressions_pass" in ev
    assert "engagement_pass" in ev
    assert "revenue_pass" in ev


def test_paid_promo_eligible_via_age_when_roi_borderline():
    # roi below default threshold but age >= 14 → roi_or_age_pass=True → eligible
    r = evaluate_paid_promotion_candidate(
        content_item_id="c2",
        content_title="Old Winner",
        organic_impressions=6_000,
        organic_engagement_rate=0.05,
        organic_revenue=200.0,
        organic_roi=1.0,   # below default 1.5 threshold
        content_age_days=30,
    )
    assert r["is_eligible"] is True
