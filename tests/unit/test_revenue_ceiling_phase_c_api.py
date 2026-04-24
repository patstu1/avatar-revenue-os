"""API behavior tests for Revenue Ceiling Phase C engines (mock-based, no DB).

These tests call the pure-function scoring engines directly — no database,
no HTTP client, no fixtures.  They validate pricing logic, gate strictness,
and the core scoring formulas from a product / integration perspective.
"""

import pytest

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
# Sponsor package pricing logic
# ---------------------------------------------------------------------------


def test_sponsor_package_pricing_logic():
    """Directly call score_sponsor_package and verify the price is in a
    sensible dollar range for a mid-size finance audience."""
    r = score_sponsor_package(
        brand_niche="finance",
        total_audience=50_000,
        avg_monthly_impressions=100_000,
        avg_engagement_rate=0.05,
        available_inventory=[],
    )
    price = r["estimated_package_price"]
    assert price > 100, f"Package price ${price:.2f} is unrealistically low"
    assert price < 100_000, f"Package price ${price:.2f} is unrealistically high"


def test_sponsor_package_price_scales_with_impressions():
    """Higher monthly impressions should yield a higher package price."""
    base = dict(brand_niche="fitness", total_audience=20_000, avg_engagement_rate=0.05, available_inventory=[])
    low_imp = score_sponsor_package(**base, avg_monthly_impressions=5_000)
    high_imp = score_sponsor_package(**base, avg_monthly_impressions=500_000)
    assert high_imp["estimated_package_price"] > low_imp["estimated_package_price"]


def test_sponsor_package_returns_deliverables_list():
    """Recommended package must always ship a non-empty deliverables list."""
    r = score_sponsor_package("tech", 30_000, 80_000, 0.04, [])
    deliverables = r["recommended_package"]["deliverables"]
    assert isinstance(deliverables, list)
    assert len(deliverables) >= 1


def test_sponsor_inventory_long_form_vs_short_form_pricing():
    """Long-form content should command a higher sponsor price than short-form
    at identical impression and engagement levels."""
    common = dict(
        content_item_id="c99",
        content_title="Deep Dive",
        niche="finance",
        impressions=25_000,
        engagement_rate=0.05,
        audience_size=80_000,
    )
    long_price = score_sponsor_inventory_item(**common, content_type="long_form")["estimated_package_price"]
    short_price = score_sponsor_inventory_item(**common, content_type="short_form")["estimated_package_price"]
    assert long_price > short_price


# ---------------------------------------------------------------------------
# Organic gate — strict signal checks
# ---------------------------------------------------------------------------

_PASSING_GATE = dict(
    content_item_id="winner_001",
    content_title="Top Finance Video",
    organic_impressions=10_000,
    organic_engagement_rate=0.06,
    organic_revenue=500.0,
    organic_roi=2.0,
    content_age_days=20,
)


def test_organic_gate_passes_when_all_signals_strong():
    """Baseline: all signals above threshold → eligible."""
    r = evaluate_paid_promotion_candidate(**_PASSING_GATE)
    assert r["is_eligible"] is True


def test_organic_gate_strict_impressions():
    """Gate is False when impressions are below the minimum threshold."""
    r = evaluate_paid_promotion_candidate(**{**_PASSING_GATE, "organic_impressions": 200})
    assert r["is_eligible"] is False


def test_organic_gate_strict_engagement():
    """Gate is False when engagement rate is below the minimum threshold."""
    r = evaluate_paid_promotion_candidate(**{**_PASSING_GATE, "organic_engagement_rate": 0.005})
    assert r["is_eligible"] is False


def test_organic_gate_strict_revenue():
    """Gate is False when organic revenue is zero — no proven monetization."""
    r = evaluate_paid_promotion_candidate(**{**_PASSING_GATE, "organic_revenue": 0.0})
    assert r["is_eligible"] is False


def test_organic_gate_strict_low_roi_and_young_content():
    """Gate is False when both ROI and content age are below thresholds
    (the gate uses roi_or_age_pass — both must fail to close this path)."""
    r = evaluate_paid_promotion_candidate(**{**_PASSING_GATE, "organic_roi": 0.5, "content_age_days": 3})
    assert r["is_eligible"] is False


def test_organic_gate_passes_on_age_alone_when_roi_low():
    """Content that has aged sufficiently (≥ 14 days) should satisfy the
    roi_or_age criterion even when ROI is below the default threshold."""
    r = evaluate_paid_promotion_candidate(**{**_PASSING_GATE, "organic_roi": 0.8, "content_age_days": 60})
    assert r["is_eligible"] is True


def test_organic_gate_gate_reason_is_non_empty_string():
    """gate_reason must always be a non-empty string for both outcomes."""
    eligible = evaluate_paid_promotion_candidate(**_PASSING_GATE)
    not_eligible = evaluate_paid_promotion_candidate(**{**_PASSING_GATE, "organic_impressions": 10})
    assert isinstance(eligible["gate_reason"], str) and eligible["gate_reason"]
    assert isinstance(not_eligible["gate_reason"], str) and not_eligible["gate_reason"]


def test_organic_gate_confidence_rises_with_passing_signals():
    """Confidence score should be higher when more signals pass the gate."""
    all_fail = evaluate_paid_promotion_candidate(
        content_item_id="cf",
        content_title="Weak Content",
        organic_impressions=10,
        organic_engagement_rate=0.001,
        organic_revenue=0.0,
        organic_roi=0.1,
        content_age_days=2,
    )
    all_pass = evaluate_paid_promotion_candidate(**_PASSING_GATE)
    assert all_pass["confidence"] > all_fail["confidence"]


# ---------------------------------------------------------------------------
# Recurring revenue scoring formula
# ---------------------------------------------------------------------------


def test_recurring_revenue_scoring_formula():
    """Annual value must exceed one month's value — recurring revenue compounds
    across a retention window that is always longer than one month."""
    r = score_recurring_revenue(
        brand_niche="fitness",
        offers=[{"id": "o1", "name": "Offer A"}, {"id": "o2", "name": "Offer B"}],
        audience_size=10_000,
        avg_content_engagement_rate=0.06,
        existing_recurring_products=[],
    )
    assert r["expected_annual_value"] > r["expected_monthly_value"], (
        f"annual={r['expected_annual_value']:.2f} should exceed monthly={r['expected_monthly_value']:.2f}"
    )


def test_recurring_revenue_best_offer_type_always_valid():
    """best_recurring_offer_type must always be drawn from the known set,
    regardless of niche or existing products."""
    for niche in ("finance", "fitness", "gaming", "unknown_niche_xyz"):
        r = score_recurring_revenue(niche, [], 5_000, 0.04, [])
        assert r["best_recurring_offer_type"] in RECURRING_OFFER_TYPES, (
            f"Unexpected offer type '{r['best_recurring_offer_type']}' for niche '{niche}'"
        )


def test_recurring_revenue_larger_audience_yields_higher_monthly():
    """All else equal, a larger audience should produce a higher monthly value."""
    small = score_recurring_revenue("finance", [], 1_000, 0.05, [])
    large = score_recurring_revenue("finance", [], 100_000, 0.05, [])
    assert large["expected_monthly_value"] > small["expected_monthly_value"]


def test_recurring_revenue_churn_reduces_annual_vs_naive_projection():
    """expected_annual_value must be less than expected_monthly_value × 12
    because the engine applies a churn discount."""
    r = score_recurring_revenue("finance", [], 20_000, 0.04, [])
    naive_annual = r["expected_monthly_value"] * 12
    assert r["expected_annual_value"] < naive_annual, "Churn should reduce annual below naive 12 × monthly projection"


# ---------------------------------------------------------------------------
# Trust conversion — uplift and deficit
# ---------------------------------------------------------------------------


def test_trust_conversion_uplift_decreases_as_trust_improves():
    """Adding more trust elements should reduce the expected conversion uplift
    (because the deficit that uplift addresses is shrinking)."""
    weak = score_trust_conversion("finance", False, False, 0, False, False, 5, 0.5, 0.02)
    strong = score_trust_conversion("finance", True, True, 10, True, True, 20, 0.8, 0.05)
    assert weak["expected_uplift"] > strong["expected_uplift"]


def test_trust_proof_blocks_have_action_field():
    """Every recommended proof block must carry an 'action' key so the
    product can render instructions to the user."""
    r = score_trust_conversion("fitness", False, False, 0, False, False, 5, 0.5, 0.02)
    for block in r["recommended_proof_blocks"]:
        assert "action" in block, f"Block missing 'action': {block}"


# ---------------------------------------------------------------------------
# Monetization mix
# ---------------------------------------------------------------------------


def test_monetization_mix_dependency_risk_is_hhi():
    """Verify the dependency risk follows HHI semantics: one method → 1.0,
    two equal methods → 0.5."""
    single = score_monetization_mix("fitness", {"affiliate": 100.0}, 100.0, 5_000, ["affiliate"])
    dual = score_monetization_mix(
        "fitness",
        {"affiliate": 50.0, "sponsorship": 50.0},
        100.0,
        5_000,
        ["affiliate", "sponsorship"],
    )
    assert single["dependency_risk"] == pytest.approx(1.0, abs=0.01)
    assert dual["dependency_risk"] == pytest.approx(0.5, abs=0.01)


def test_monetization_mix_next_best_mix_caps_at_40_pct():
    """No single method in next_best_mix should exceed 0.40 — the engine
    enforces a 40 % cap to prevent re-concentration."""
    r = score_monetization_mix(
        "fitness",
        {"affiliate": 950.0, "ads": 50.0},
        1000.0,
        10_000,
        ["affiliate", "ads"],
    )
    for method, share in r["next_best_mix"].items():
        assert share <= 0.41, f"{method} share {share:.4f} exceeds 40 % cap"
