"""Unit tests for scoring engines — opportunity, forecast, offer fit, saturation."""
import pytest

from packages.scoring.forecast import ForecastInput, compute_profit_forecast
from packages.scoring.offer_fit import OfferFitInput, compute_offer_fit
from packages.scoring.opportunity import WEIGHTS, OpportunityInput, compute_opportunity_score
from packages.scoring.saturation import SaturationInput, compute_saturation


class TestOpportunityScoring:
    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    def test_zero_input_gives_zero(self):
        result = compute_opportunity_score(OpportunityInput())
        assert result.composite_score == 0.0
        assert result.confidence == "insufficient"

    def test_strong_signals_produce_high_score(self):
        inp = OpportunityInput(
            buyer_intent=0.9, trend_velocity=0.8, trend_acceleration=0.7,
            content_gap=0.8, historical_win_rate=0.7, offer_fit=0.85,
            expected_profit_score=0.9, platform_suitability=0.8,
        )
        result = compute_opportunity_score(inp)
        assert result.composite_score > 0.7
        assert result.confidence == "high"

    def test_penalties_reduce_score(self):
        base_inp = OpportunityInput(
            buyer_intent=0.8, trend_velocity=0.7, content_gap=0.6,
            offer_fit=0.7, expected_profit_score=0.8, platform_suitability=0.7,
        )
        base = compute_opportunity_score(base_inp)

        penalized_inp = OpportunityInput(
            buyer_intent=0.8, trend_velocity=0.7, content_gap=0.6,
            offer_fit=0.7, expected_profit_score=0.8, platform_suitability=0.7,
            saturation_penalty=0.2, audience_fatigue_penalty=0.15,
        )
        penalized = compute_opportunity_score(penalized_inp)
        assert penalized.composite_score < base.composite_score

    def test_boosts_increase_score(self):
        base_inp = OpportunityInput(buyer_intent=0.5, trend_velocity=0.5)
        base = compute_opportunity_score(base_inp)

        boosted_inp = OpportunityInput(
            buyer_intent=0.5, trend_velocity=0.5,
            seasonal_boost=0.1, brand_fit_boost=0.05,
        )
        boosted = compute_opportunity_score(boosted_inp)
        assert boosted.composite_score > base.composite_score

    def test_trending_only_not_enough(self):
        """A topic that is only trending (no buyer intent, no offer fit) should not score high."""
        inp = OpportunityInput(trend_velocity=1.0, trend_acceleration=1.0)
        result = compute_opportunity_score(inp)
        assert result.composite_score < 0.5
        assert result.confidence in ("low", "insufficient")

    def test_explanation_contains_drivers(self):
        inp = OpportunityInput(buyer_intent=0.9, offer_fit=0.8)
        result = compute_opportunity_score(inp)
        assert "buyer_intent" in result.explanation

    def test_score_clamped_to_0_1(self):
        inp = OpportunityInput(
            buyer_intent=1.0, trend_velocity=1.0, trend_acceleration=1.0,
            content_gap=1.0, historical_win_rate=1.0, offer_fit=1.0,
            expected_profit_score=1.0, platform_suitability=1.0,
            seasonal_boost=0.15, brand_fit_boost=0.10,
        )
        result = compute_opportunity_score(inp)
        assert result.composite_score <= 1.0


class TestForecast:
    def test_zero_input(self):
        result = compute_profit_forecast(ForecastInput())
        assert result.expected_profit == 0.0
        assert result.confidence == "insufficient"

    def test_basic_forecast(self):
        inp = ForecastInput(
            expected_impressions=10000, expected_ctr=0.03,
            expected_conversion_rate=0.04, expected_value_per_conversion=50.0,
            expected_generation_cost=3.0, expected_distribution_cost=1.0,
        )
        result = compute_profit_forecast(inp)
        assert result.expected_clicks == 300
        assert result.expected_conversions == 12.0
        assert result.expected_revenue == 600.0
        assert result.expected_cost == 4.0
        assert result.expected_profit == 596.0
        assert result.confidence == "high"

    def test_costs_reduce_profit(self):
        base = compute_profit_forecast(ForecastInput(
            expected_impressions=5000, expected_ctr=0.02,
            expected_conversion_rate=0.03, expected_value_per_conversion=30.0,
        ))
        with_costs = compute_profit_forecast(ForecastInput(
            expected_impressions=5000, expected_ctr=0.02,
            expected_conversion_rate=0.03, expected_value_per_conversion=30.0,
            expected_generation_cost=10.0, fatigue_penalty_dollars=5.0,
        ))
        assert with_costs.expected_profit < base.expected_profit

    def test_rpm_calculation(self):
        result = compute_profit_forecast(ForecastInput(
            expected_impressions=1000, expected_ctr=0.05,
            expected_conversion_rate=0.10, expected_value_per_conversion=20.0,
        ))
        assert result.expected_rpm == 100.0

    def test_explanation_present(self):
        result = compute_profit_forecast(ForecastInput(
            expected_impressions=1000, expected_ctr=0.02,
            expected_conversion_rate=0.03, expected_value_per_conversion=25.0,
        ))
        assert "impressions" in result.explanation
        assert "profit" in result.explanation


class TestOfferFit:
    def test_no_input(self):
        result = compute_offer_fit(OfferFitInput(
            topic_keywords=[], offer_audience_tags=[],
            offer_niche_relevance=0.0, topic_buyer_intent=0.0,
        ))
        assert result.confidence == "insufficient"

    def test_good_fit(self):
        result = compute_offer_fit(OfferFitInput(
            topic_keywords=["budgeting", "savings", "finance"],
            offer_audience_tags=["budgeting", "savings", "millennials"],
            offer_epc=3.0, offer_conversion_rate=0.06, offer_payout=45.0,
            topic_buyer_intent=0.8, offer_niche_relevance=0.8,
        ))
        assert result.fit_score > 0.5
        assert result.confidence in ("high", "medium")

    def test_platform_restriction_increases_friction(self):
        no_restriction = compute_offer_fit(OfferFitInput(
            topic_keywords=["test"], offer_audience_tags=["test"],
            offer_epc=2.0, topic_buyer_intent=0.5,
        ))
        with_restriction = compute_offer_fit(OfferFitInput(
            topic_keywords=["test"], offer_audience_tags=["test"],
            offer_epc=2.0, topic_buyer_intent=0.5,
            platform="tiktok", offer_platform_restrictions=["youtube"],
        ))
        assert with_restriction.friction_score > no_restriction.friction_score

    def test_explanation_present(self):
        result = compute_offer_fit(OfferFitInput(
            topic_keywords=["test"], offer_audience_tags=["test"],
            offer_epc=1.0, topic_buyer_intent=0.5,
        ))
        assert "audience_alignment" in result.explanation


class TestSaturation:
    def test_no_activity(self):
        result = compute_saturation(SaturationInput())
        assert result.saturation_score < 0.3
        assert result.recommended_action == "maintain"

    def test_high_saturation(self):
        result = compute_saturation(SaturationInput(
            unique_topics_covered=18, total_topics_available=20,
            posts_last_7d=21, posts_last_30d=60,
            similar_content_count=8, audience_overlap_pct=0.7,
        ))
        assert result.saturation_score > 0.5
        assert result.recommended_action in ("suppress", "reduce")

    def test_engagement_decline_causes_fatigue(self):
        result = compute_saturation(SaturationInput(
            avg_engagement_last_7d=2.0, avg_engagement_last_30d=5.0,
        ))
        assert result.fatigue_score > 0.3

    def test_originality_inversely_related_to_similarity(self):
        result = compute_saturation(SaturationInput(max_similarity_score=0.8))
        assert result.originality_score == pytest.approx(0.2)

    def test_explanation_present(self):
        result = compute_saturation(SaturationInput(posts_last_7d=5))
        assert "saturation" in result.explanation.lower()
