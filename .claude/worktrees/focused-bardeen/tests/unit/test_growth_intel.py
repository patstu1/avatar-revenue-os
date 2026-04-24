"""Unit tests for Phase 6 growth_intel rules engines."""

from packages.scoring.growth_intel import (
    ContentPerfRollup,
    cluster_segments_rules,
    detect_leaks,
    estimate_ltv_rules,
    geo_language_expansion_rules,
    paid_amplification_candidates,
    plan_cross_platform_derivatives,
    trust_score_for_account,
)
from packages.scoring.winner import ContentPerformance


def test_cluster_segments_groups_by_dimensions():
    accounts = [
        {
            "id": "a1",
            "platform": "youtube",
            "geography": "US",
            "language": "en",
            "niche_focus": "finance",
            "is_active": True,
            "follower_count": 1000,
        }
    ]
    perf = {"a1": {"revenue": 50.0, "profit": 10.0, "impressions": 5000}}
    out = cluster_segments_rules(accounts, perf)
    assert len(out) == 1
    assert out[0]["segment_criteria"]["phase6_auto"] is True
    assert out[0]["segment_criteria"]["platform"] == "youtube"


def test_estimate_ltv_rules_dimensions_in_parameters():
    offer = {
        "id": "o1",
        "payout_amount": 40.0,
        "average_order_value": 80.0,
        "conversion_rate": 0.03,
        "recurring_commission": False,
        "priority": 1,
    }
    row = estimate_ltv_rules(offer, "youtube", "US", "en", "topic", "seg", "organic", 0.02)
    assert row["model_type"] == "rules_based_phase6"
    assert row["estimated_ltv_365d"] >= row["estimated_ltv_30d"]
    dims = row["parameters"]["dimensions"]
    assert dims["platform"] == "youtube"
    assert dims["offer_id"] == "o1"


def test_detect_leaks_high_views_low_clicks():
    items = [
        ContentPerfRollup(
            content_id="c1",
            title="t",
            brand_id="b",
            creator_account_id="a",
            platform="youtube",
            offer_id="o1",
            impressions=5000,
            clicks=20,
            ctr=0.004,
            conversions=0,
            conversion_rate=0.0,
        )
    ]
    offer_by_id = {"o1": {"epc": 3.0, "conversion_rate": 0.02}}
    leaks = detect_leaks(items, 1000, 50, 1, offer_by_id, {})
    types = {x["leak_type"] for x in leaks}
    assert "high_views_low_clicks" in types


def test_detect_leaks_brand_funnel():
    items: list[ContentPerfRollup] = []
    leaks = detect_leaks(items, 8000, 40, 0, {}, {})
    assert any(l.get("entity_type") == "brand_funnel" for l in leaks)


def test_geo_language_expansion_from_single_geo():
    accounts = [{"geography": "US", "language": "en", "platform": "youtube"}]
    recs = geo_language_expansion_rules(accounts, "crypto")
    assert any(r["target_language"] == "es" for r in recs)


def test_paid_amplification_only_winners():
    items = [
        ContentPerformance(
            content_id="c1",
            title="Winner post",
            impressions=50_000,
            revenue=800.0,
            profit=120.0,
            rpm=18.0,
            ctr=0.04,
            engagement_rate=0.08,
            conversion_rate=0.04,
            platform="youtube",
            account_id="a1",
        )
    ]
    candidates = paid_amplification_candidates(items, set())
    assert len(candidates) >= 1
    assert candidates[0]["content_item_id"] == "c1"
    assert candidates[0]["is_candidate"] is True


def test_paid_amplification_skips_existing():
    items = [
        ContentPerformance(
            content_id="c1",
            title="Winner post",
            impressions=50_000,
            revenue=800.0,
            profit=120.0,
            rpm=18.0,
            ctr=0.04,
            engagement_rate=0.08,
            conversion_rate=0.04,
            platform="youtube",
            account_id="a1",
        )
    ]
    assert paid_amplification_candidates(items, {"c1"}) == []


def test_plan_cross_platform_derivatives_winner():
    items = [
        ContentPerformance(
            content_id="w1",
            title="Viral",
            impressions=40_000,
            revenue=600.0,
            profit=90.0,
            rpm=15.0,
            ctr=0.035,
            engagement_rate=0.06,
            conversion_rate=0.03,
            platform="youtube",
            account_id="a1",
        )
    ]
    plans = plan_cross_platform_derivatives(items, {"youtube"})
    assert any(p["target_platform"] == "tiktok" for p in plans)


def test_trust_scoring_in_range():
    acct = {
        "platform": "youtube",
        "account_health": "healthy",
        "posting_capacity_per_day": 2,
        "originality_drift_score": 0.1,
        "fatigue_score": 0.1,
        "follower_count": 5000,
    }
    out = trust_score_for_account(acct, {"engagement_rate": 0.05})
    assert 0 <= out["trust_score"] <= 100
    assert "health" in out["components"]
    assert isinstance(out["recommendations"], list)
