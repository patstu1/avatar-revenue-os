"""Unit tests — elite revenue upgrades: viral reactor, revenue optimization, CTA, engagement, forecast."""
from __future__ import annotations

# ── Revenue Optimization Engine ──

def test_score_revenue_potential():
    from packages.scoring.revenue_optimization_engine import score_revenue_potential
    result = score_revenue_potential(offer_payout=50, historical_cvr=0.03, estimated_impressions=10000, monetization_density=0.8)
    assert result["expected_revenue"] > 0
    assert result["affiliate_component"] > 0


def test_rank_briefs_by_revenue():
    from packages.scoring.revenue_optimization_engine import rank_briefs_by_revenue
    briefs = [
        {"title": "Low rev", "offer_payout": 5, "historical_cvr": 0.01, "estimated_impressions": 500},
        {"title": "High rev", "offer_payout": 100, "historical_cvr": 0.05, "estimated_impressions": 20000},
        {"title": "Med rev", "offer_payout": 30, "historical_cvr": 0.02, "estimated_impressions": 5000},
    ]
    ranked = rank_briefs_by_revenue(briefs, niche="personal_finance")
    assert ranked[0]["title"] == "High rev"
    assert ranked[-1]["title"] == "Low rev"


def test_should_prioritize_monetized():
    from packages.scoring.revenue_optimization_engine import should_prioritize_monetized
    assert should_prioritize_monetized(50, 0.5) is True
    assert should_prioritize_monetized(5, 0.9) is False


# ── CTA Engine ──

def test_select_cta_basic():
    from packages.scoring.cta_engine import select_cta
    cta = select_cta("youtube")
    assert "text" in cta
    assert "style" in cta
    assert "id" in cta


def test_select_cta_with_offer():
    from packages.scoring.cta_engine import select_cta
    cta = select_cta("tiktok", has_offer=True)
    assert cta["text"]


def test_select_cta_with_lead_magnet():
    from packages.scoring.cta_engine import select_cta
    cta = select_cta("instagram", has_lead_magnet=True)
    assert cta["style"] == "lead_capture"


def test_get_all_cta_ids():
    from packages.scoring.cta_engine import get_all_cta_ids
    ids = get_all_cta_ids("youtube")
    assert len(ids) >= 4
    assert all(isinstance(i, str) for i in ids)


def test_cta_all_platforms_have_templates():
    from packages.scoring.cta_engine import CTA_LIBRARY
    for platform in ["youtube", "tiktok", "instagram", "x", "linkedin"]:
        assert len(CTA_LIBRARY[platform]) >= 4


# ── Engagement Automation Engine ──

def test_engagement_plan_seed():
    from packages.scoring.engagement_automation_engine import generate_engagement_plan
    plan = generate_engagement_plan("seed", "youtube", "personal_finance")
    assert len(plan["actions"]) >= 3
    assert len(plan["comments"]) >= 2
    action_types = [a["type"] for a in plan["actions"]]
    assert "follow" in action_types
    assert "like" in action_types
    assert "comment" in action_types


def test_engagement_plan_trickle():
    from packages.scoring.engagement_automation_engine import generate_engagement_plan
    plan = generate_engagement_plan("trickle", "tiktok", "health_fitness")
    assert len(plan["actions"]) >= 1


def test_engagement_plan_scale_returns_empty():
    from packages.scoring.engagement_automation_engine import generate_engagement_plan
    plan = generate_engagement_plan("scale", "youtube", "tech_reviews")
    assert plan["actions"] == []


def test_contextual_comment():
    from packages.scoring.engagement_automation_engine import generate_contextual_comment
    comment = generate_contextual_comment("personal_finance", "How I saved $10K in 6 months")
    assert len(comment) > 10
    assert isinstance(comment, str)


# ── Revenue Forecast Engine ──

def test_forecast_insufficient_data():
    from packages.scoring.revenue_forecast_engine import forecast_revenue
    result = forecast_revenue([10, 20, 30], planned_posts_per_day=5)
    assert result["confidence"] == "low"
    assert result["forecast_revenue_30d"] == 0


def test_forecast_with_data():
    from packages.scoring.revenue_forecast_engine import forecast_revenue
    daily = [10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 32.0, 35.0, 38.0, 40.0, 42.0]
    result = forecast_revenue(daily, planned_posts_per_day=10, accounts_active=25)
    assert result["forecast_revenue_30d"] > 0
    assert result["confidence"] == "medium"
    assert result["trend_direction"] == "up"


def test_forecast_with_expansion():
    from packages.scoring.revenue_forecast_engine import forecast_revenue
    daily = [50.0] * 14
    result = forecast_revenue(daily, accounts_active=25, accounts_planned=5)
    assert result["expansion_uplift"] > 0
    assert result["forecast_revenue_30d"] > 50 * 30 * 0.5


def test_forecast_summary():
    from packages.scoring.revenue_forecast_engine import forecast_revenue, generate_forecast_summary
    daily = [100.0] * 30
    result = forecast_revenue(daily)
    summary = generate_forecast_summary(result)
    assert "$" in summary
    assert "confidence" in summary.lower()


def test_linear_trend():
    from packages.scoring.revenue_forecast_engine import linear_trend
    slope, intercept = linear_trend([10, 20, 30, 40, 50])
    assert slope > 0
    assert abs(slope - 10) < 0.1


def test_forecast_by_niche():
    from packages.scoring.revenue_forecast_engine import forecast_by_niche
    data = {
        "personal_finance": [20.0] * 14,
        "ai_tools": [50.0] * 14,
    }
    results = forecast_by_niche(data)
    assert "personal_finance" in results
    assert "ai_tools" in results
    assert results["ai_tools"]["forecast_revenue_30d"] > results["personal_finance"]["forecast_revenue_30d"]


# ── Lead Magnet Service ──

def test_nurture_sequence():
    from apps.api.services.lead_magnet_service import build_full_nurture_sequence
    seq = build_full_nurture_sequence("Budgeting 101", "checklist", "BudgetApp Pro")
    assert len(seq) == 6
    assert seq[0]["day"] == 0
    assert seq[0]["type"] == "welcome"
    assert "Budgeting 101" in seq[0]["subject"]
    monetize_steps = [s for s in seq if s["type"] == "monetize"]
    assert len(monetize_steps) >= 1
    assert monetize_steps[0]["offer_name"] == "BudgetApp Pro"


def test_lead_magnet_types():
    from apps.api.services.lead_magnet_service import LEAD_MAGNET_TYPES
    assert len(LEAD_MAGNET_TYPES) >= 5
    types = [m["type"] for m in LEAD_MAGNET_TYPES]
    assert "checklist" in types
    assert "guide" in types
