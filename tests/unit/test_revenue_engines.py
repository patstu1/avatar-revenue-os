"""Unit tests for revenue ceiling engines."""

from packages.scoring.revenue_engines import (
    REVENUE_INTEL_SOURCE,
    estimate_owned_audience_value,
    optimize_offer_stack,
    recommend_productization,
    score_funnel_paths,
    score_monetization_density,
)


def _offers():
    return [
        {"id": "o1", "name": "Affiliate A", "payout_amount": 40.0, "conversion_rate": 0.03, "monetization_method": "affiliate", "audience_fit_tags": ["finance"], "epc": 2.5, "average_order_value": 80.0, "recurring_commission": False},
        {"id": "o2", "name": "Course B", "payout_amount": 97.0, "conversion_rate": 0.015, "monetization_method": "course", "audience_fit_tags": [], "epc": 1.5, "average_order_value": 97.0, "recurring_commission": False},
        {"id": "o3", "name": "Membership C", "payout_amount": 19.0, "conversion_rate": 0.05, "monetization_method": "membership", "audience_fit_tags": [], "epc": 1.0, "average_order_value": 19.0, "recurring_commission": True},
    ]


def test_offer_stack_returns_ranked_combos():
    content = {"id": "c1", "title": "Test Video"}
    stacks = optimize_offer_stack(content, _offers(), None)
    assert len(stacks) == 3
    assert stacks[0]["combined_expected_revenue"] >= stacks[1]["combined_expected_revenue"]
    assert stacks[0]["primary_offer_id"] is not None
    assert len(stacks[0]["offer_stack"]) >= 1
    assert REVENUE_INTEL_SOURCE in stacks[0]


def test_offer_stack_includes_secondary_and_downsell():
    content = {"id": "c1", "title": "Test"}
    stacks = optimize_offer_stack(content, _offers(), None)
    best = stacks[0]
    assert len(best["offer_stack"]) >= 2
    assert best["expected_aov_uplift_pct"] > 0


def test_offer_stack_evidence_recorded():
    stacks = optimize_offer_stack({"id": "c1", "title": "T"}, _offers(), None)
    ev = stacks[0]["evidence"]
    assert "primary_expected" in ev
    assert "offers_considered" in ev
    assert ev["offers_considered"] == 3


def test_offer_stack_segment_fit_multiplier():
    seg = {"segment_criteria": {"niche_focus": "finance investing"}}
    stacks = optimize_offer_stack({"id": "c1", "title": "T"}, _offers(), seg)
    assert stacks[0]["segment_fit_multiplier"] >= 1.0


def test_funnel_path_scoring_detects_underperformance():
    paths = [
        {"content_id": "c1", "offer_id": "o1", "stages": {"click": 100, "opt_in": 40, "purchase": 2}, "total_clicks": 100, "total_conversions": 2, "revenue": 80, "avg_event_value": 40.0},
    ]
    results = score_funnel_paths(paths, 0.05)
    assert len(results) == 1
    assert results[0]["efficiency_vs_brand_avg"] < 1.0
    assert results[0]["drop_off_stage"] is not None
    assert REVENUE_INTEL_SOURCE in results[0]


def test_funnel_path_evidence_has_stages():
    paths = [{"content_id": "c1", "offer_id": "o1", "stages": {"click": 50, "purchase": 5}, "total_clicks": 50, "total_conversions": 5, "revenue": 200, "avg_event_value": 40}]
    results = score_funnel_paths(paths, 0.05)
    assert "stages" in results[0]["evidence"]


def test_owned_audience_value_channels():
    result = estimate_owned_audience_value(
        opt_in_count=1000, subscriber_count=5000, membership_count=50,
        avg_revenue_per_subscriber=0.5, repeat_purchase_rate=0.15,
        offers=[{"payout_amount": 40.0}],
    )
    assert "email" in result["channels"]
    assert "subscribers" in result["channels"]
    assert "membership" in result["channels"]
    assert result["total_owned_audience_value"] > 0
    assert REVENUE_INTEL_SOURCE in result


def test_owned_audience_recommends_actions_when_small():
    result = estimate_owned_audience_value(
        opt_in_count=100, subscriber_count=200, membership_count=0,
        avg_revenue_per_subscriber=0.1, repeat_purchase_rate=0.05,
        offers=[{"payout_amount": 20.0}],
    )
    assert len(result["recommended_actions"]) >= 1


def test_productization_course_recommendation():
    winners = [{"title": "Top Video", "win_score": 0.9, "content_id": "c1"}] * 3
    recs = recommend_productization(winners, [{"estimated_size": 10000}], [{"monetization_method": "affiliate"}], 5, 5000.0, 2000)
    course_recs = [r for r in recs if r["product_type"] == "course"]
    assert len(course_recs) >= 1
    assert course_recs[0]["expected_revenue"] > 0
    assert course_recs[0]["expected_cost"] > 0
    assert course_recs[0]["break_even_units"] > 0
    assert REVENUE_INTEL_SOURCE in course_recs[0]


def test_productization_includes_consulting_for_established():
    winners = [{"title": f"W{i}", "win_score": 0.8, "content_id": f"c{i}"} for i in range(5)]
    recs = recommend_productization(winners, [], [{"monetization_method": "affiliate"}], 0, 8000.0, 3000)
    types = {r["product_type"] for r in recs}
    assert "consulting" in types


def test_productization_skips_existing_methods():
    recs = recommend_productization(
        [{"title": "W", "win_score": 0.9, "content_id": "c1"}] * 3,
        [], [{"monetization_method": "course"}, {"monetization_method": "membership"}, {"monetization_method": "consulting"}, {"monetization_method": "lead_gen"}],
        0, 10000, 5000,
    )
    assert len(recs) == 0


def test_density_scoring_full_layers():
    d = score_monetization_density(
        "c1", "Full Stack", True, True, True, True, True, True, True, True, 500.0, 50000,
    )
    assert d["density_score"] > 80
    assert d["layer_count"] == 8
    assert len(d["missing_layers"]) == 0
    assert REVENUE_INTEL_SOURCE in d


def test_density_scoring_sparse_layers():
    d = score_monetization_density(
        "c2", "Bare Post", True, False, False, False, False, False, False, False, 10.0, 5000,
    )
    assert d["density_score"] < 30
    assert d["layer_count"] == 1
    assert len(d["missing_layers"]) == 7
    assert len(d["recommended_additions"]) >= 1


def test_density_evidence_includes_rpm():
    d = score_monetization_density("c1", "T", True, True, False, False, False, False, False, False, 100.0, 10000)
    assert "rpm" in d["evidence"]
    assert d["evidence"]["rpm"] == 10.0
