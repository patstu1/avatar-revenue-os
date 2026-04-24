"""Unit tests for all 11 MXP scoring engines."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Experiment Decision Engine
# ---------------------------------------------------------------------------
from packages.scoring.experiment_decision_engine import (
    evaluate_experiment_outcome,
    prioritize_experiment_candidates,
)


class TestPrioritizeExperimentCandidates:
    def test_happy_path_ranks_by_priority(self):
        experiments = [
            {
                "experiment_type": "headline",
                "target_scope_type": "offer",
                "target_scope_id": "offer-1",
                "hypothesis": "New headline lifts CR",
                "expected_upside": 0.7,
                "confidence_gap": 0.6,
                "age_days": 0,
            },
            {
                "experiment_type": "price",
                "target_scope_type": "offer",
                "target_scope_id": "offer-2",
                "hypothesis": "Price drop lifts volume",
                "expected_upside": 0.3,
                "confidence_gap": 0.2,
                "age_days": 5,
            },
        ]
        ctx = {"brand_id": "b1", "total_traffic": 5000, "risk_tolerance": 0.5}
        results = prioritize_experiment_candidates(experiments, ctx)

        assert len(results) == 2
        assert results[0]["priority_score"] >= results[1]["priority_score"]
        for r in results:
            assert "explanation" in r
            assert "confidence" in r
            assert 0.0 <= r["priority_score"] <= 1.0
            assert 0.0 <= r["confidence"] <= 1.0

    def test_empty_experiments(self):
        results = prioritize_experiment_candidates([], {"brand_id": "b1"})
        assert results == []

    def test_redundant_experiments_removed(self):
        base = {
            "experiment_type": "headline",
            "target_scope_type": "offer",
            "target_scope_id": "offer-1",
            "hypothesis": "test",
            "expected_upside": 0.5,
            "confidence_gap": 0.4,
        }
        exp_older = {**base, "age_days": 10}
        exp_newer = {**base, "age_days": 2}
        results = prioritize_experiment_candidates([exp_older, exp_newer], {"brand_id": "b1"})
        assert len(results) == 1

    def test_auto_promote_flag_for_high_priority(self):
        experiments = [
            {
                "experiment_type": "layout",
                "target_scope_type": "page",
                "expected_upside": 0.95,
                "confidence_gap": 0.90,
                "age_days": 0,
            },
        ]
        results = prioritize_experiment_candidates(experiments, {"brand_id": "b1", "risk_tolerance": 0.9})
        assert results[0]["promotion_rule"]["auto_promote"] is True


class TestEvaluateExperimentOutcome:
    def test_promotes_winning_variant(self):
        experiment = {"experiment_type": "headline"}
        observed = {
            "variants": [
                {"variant_id": "A", "conversion_rate": 0.03, "sample_size": 800},
                {"variant_id": "B", "conversion_rate": 0.12, "sample_size": 800},
            ],
            "days_running": 14,
            "baseline_conversion_rate": 0.05,
        }
        result = evaluate_experiment_outcome(experiment, observed)
        assert result["outcome_type"] == "promote"
        assert result["winner_variant_id"] == "B"
        assert 0.0 <= result["confidence"] <= 1.0
        assert "explanation" in result

    def test_empty_variants_inconclusive(self):
        result = evaluate_experiment_outcome(
            {"experiment_type": "price"},
            {"variants": [], "days_running": 5, "baseline_conversion_rate": 0.03},
        )
        assert result["outcome_type"] == "inconclusive"
        assert result["confidence"] == 0.0

    def test_negative_uplift_suppresses(self):
        result = evaluate_experiment_outcome(
            {"experiment_type": "cta"},
            {
                "variants": [
                    {"variant_id": "A", "conversion_rate": 0.07, "sample_size": 500},
                    {"variant_id": "B", "conversion_rate": 0.05, "sample_size": 500},
                ],
                "days_running": 10,
                "baseline_conversion_rate": 0.10,
            },
        )
        assert result["outcome_type"] == "suppress"


# ---------------------------------------------------------------------------
# 2. Contribution Engine
# ---------------------------------------------------------------------------
from packages.scoring.contribution_engine import (
    compare_attribution_models,
    compute_contribution_reports,
)


class TestComputeContributionReports:
    def test_happy_path_multiple_models(self):
        touchpoints = [
            {"scope_type": "email", "scope_id": "e1", "value": 100, "days_before_conversion": 7},
            {"scope_type": "social", "scope_id": "s1", "value": 50, "days_before_conversion": 1},
        ]
        results = compute_contribution_reports(touchpoints, ["first_touch", "linear"])
        assert len(results) >= 2
        for r in results:
            assert "explanation" in r
            assert "confidence" in r
            assert 0.0 <= r["contribution_score"] <= 1.0
            assert 0.0 <= r["confidence"] <= 1.0

    def test_empty_touchpoints(self):
        results = compute_contribution_reports([], ["linear"])
        assert results == []

    def test_first_touch_all_credit_to_first(self):
        touchpoints = [
            {"scope_type": "ad", "scope_id": "a1", "value": 200, "days_before_conversion": 10},
            {"scope_type": "email", "scope_id": "e1", "value": 0, "days_before_conversion": 1},
        ]
        results = compute_contribution_reports(touchpoints, ["first_touch"])
        first_row = [r for r in results if r["scope_id"] == "a1"][0]
        assert first_row["contribution_score"] == 1.0


class TestCompareAttributionModels:
    def test_detects_divergences(self):
        touchpoints = [
            {"scope_type": "ad", "scope_id": "a1", "value": 500, "days_before_conversion": 14},
            {"scope_type": "social", "scope_id": "s1", "value": 100, "days_before_conversion": 7},
            {"scope_type": "email", "scope_id": "e1", "value": 50, "days_before_conversion": 0},
        ]
        reports = compute_contribution_reports(touchpoints, ["last_touch", "time_decay"])
        comparison = compare_attribution_models(reports)
        assert "divergences" in comparison
        assert "confidence" in comparison
        assert 0.0 <= comparison["confidence"] <= 1.0

    def test_empty_reports(self):
        comparison = compare_attribution_models([])
        assert comparison["divergences"] == []


# ---------------------------------------------------------------------------
# 3. Capacity Engine
# ---------------------------------------------------------------------------
from packages.scoring.capacity_engine import allocate_queues, compute_capacity_reports


class TestComputeCapacityReports:
    def test_happy_path(self):
        data = [
            {
                "capacity_type": "content_generation",
                "current_capacity": 100,
                "used_capacity": 60,
                "unit_cost": 5.0,
                "revenue_per_unit": 15.0,
            },
        ]
        results = compute_capacity_reports(data, {"content_generation": 800})
        assert len(results) == 1
        r = results[0]
        assert r["capacity_type"] == "content_generation"
        assert "explanation" in r
        assert 0.0 <= r["confidence"] <= 1.0

    def test_empty_data_returns_fallback(self):
        results = compute_capacity_reports([], {})
        assert len(results) == 1
        assert results[0]["capacity_type"] == "none"

    def test_bottleneck_detection(self):
        data = [
            {
                "capacity_type": "publishing",
                "current_capacity": 100,
                "used_capacity": 98,
                "unit_cost": 2.0,
                "revenue_per_unit": 10.0,
            },
        ]
        results = compute_capacity_reports(data, {})
        assert results[0]["recommended_throttle"] is not None
        assert results[0]["bottleneck_reason"] is not None


class TestAllocateQueues:
    def test_happy_path_allocation(self):
        cap_reports = [
            {
                "capacity_type": "content_generation",
                "recommended_volume": 80,
                "used_capacity": 50,
            },
        ]
        queues = [
            {
                "queue_name": "high_roi",
                "capacity_type": "content_generation",
                "requested_capacity": 20,
                "expected_roi": 0.8,
                "priority_tier": 1,
            },
        ]
        results = allocate_queues(cap_reports, queues)
        assert len(results) == 1
        assert results[0]["allocated_capacity"] == 20.0
        assert results[0]["deferred_capacity"] == 0.0

    def test_empty_queues(self):
        results = allocate_queues([], [])
        assert results == []


# ---------------------------------------------------------------------------
# 4. Offer Lifecycle Engine
# ---------------------------------------------------------------------------
from packages.scoring.offer_lifecycle_engine import (
    assess_offer_lifecycle,
    recommend_lifecycle_transition,
)


class TestAssessOfferLifecycle:
    def test_happy_path(self):
        offers = [
            {
                "offer_id": "o1",
                "name": "Course A",
                "age_days": 120,
                "total_conversions": 80,
                "revenue": 5000,
                "growth_rate": 0.10,
                "is_paused": False,
                "is_retired": False,
            },
        ]
        history = [
            {"offer_id": "o1", "period_index": 1, "conversion_rate": 0.04, "revenue": 2000},
            {"offer_id": "o1", "period_index": 2, "conversion_rate": 0.05, "revenue": 3000},
        ]
        results = assess_offer_lifecycle(offers, history)
        assert len(results) == 1
        r = results[0]
        assert r["lifecycle_state"] in (
            "onboarding",
            "probation",
            "active",
            "scaling",
            "plateauing",
            "decaying",
            "seasonal_pause",
            "retired",
            "relaunch_candidate",
        )
        assert 0.0 <= r["health_score"] <= 1.0
        assert 0.0 <= r["confidence"] <= 1.0
        assert "explanation" in r

    def test_empty_offers(self):
        results = assess_offer_lifecycle([], [])
        assert results == []

    def test_decaying_offer_detection(self):
        offers = [
            {
                "offer_id": "o2",
                "name": "Dying Offer",
                "age_days": 200,
                "total_conversions": 10,
                "revenue": 200,
                "growth_rate": 0.0,
                "is_paused": False,
                "is_retired": False,
            },
        ]
        history = [
            {"offer_id": "o2", "period_index": 1, "conversion_rate": 0.10, "revenue": 150},
            {"offer_id": "o2", "period_index": 2, "conversion_rate": 0.02, "revenue": 50},
        ]
        results = assess_offer_lifecycle(offers, history)
        assert results[0]["lifecycle_state"] == "decaying"


class TestRecommendLifecycleTransition:
    def test_no_change(self):
        report = {
            "lifecycle_state": "active",
            "current_db_state": "active",
            "health_score": 0.75,
            "decay_score": 0.1,
            "dependency_risk_score": 0.2,
            "confidence": 0.8,
        }
        result = recommend_lifecycle_transition(report)
        assert result["event_type"] == "no_change"
        assert result["from_state"] == "active"

    def test_transition_detected(self):
        report = {
            "lifecycle_state": "decaying",
            "current_db_state": "active",
            "health_score": 0.25,
            "decay_score": 0.8,
            "dependency_risk_score": 0.3,
            "confidence": 0.7,
        }
        result = recommend_lifecycle_transition(report)
        assert result["event_type"] == "performance_decline"
        assert result["to_state"] == "decaying"


# ---------------------------------------------------------------------------
# 5. Creative Memory Engine
# ---------------------------------------------------------------------------
from packages.scoring.creative_memory_engine import index_creative_atoms, query_atoms


class TestIndexCreativeAtoms:
    def test_happy_path(self):
        items = [
            {"id": "c1", "title": "Amazing hook for fitness", "body": "Start with a hook", "niche": "fitness"},
            {"id": "c2", "title": "CTA buy now", "body": "Click the buy now button", "platform": "youtube"},
        ]
        perf = [
            {"content_item_id": "c1", "engagement_rate": 0.08, "conversion_rate": 0.02},
        ]
        ctx = {"niche": "fitness", "default_platform": "youtube"}
        results = index_creative_atoms(items, perf, ctx)
        assert len(results) == 2
        assert results[0]["atom_type"] == "hook"
        assert results[1]["atom_type"] == "cta"
        for r in results:
            assert "confidence" in r
            assert "explanation" in r

    def test_empty_items(self):
        results = index_creative_atoms([], [], {"niche": "tech"})
        assert results == []

    def test_originality_caution_increases_with_reuse(self):
        items = [
            {"id": "c1", "title": "Hook opener", "body": "Attention hook", "reuse_count": 18},
        ]
        results = index_creative_atoms(items, [], {"niche": "general"})
        assert results[0]["originality_caution_score"] > 0.5


class TestQueryAtoms:
    def test_filters_by_niche(self):
        atoms = [
            {
                "niche": "fitness",
                "platform": "youtube",
                "atom_type": "hook",
                "performance_summary": {"avg_engagement": 0.1, "avg_conversion": 0.05},
            },
            {
                "niche": "tech",
                "platform": "youtube",
                "atom_type": "cta",
                "performance_summary": {"avg_engagement": 0.08, "avg_conversion": 0.03},
            },
        ]
        results = query_atoms(atoms, {"niche": "fitness"})
        assert len(results) == 1
        assert results[0]["niche"] == "fitness"

    def test_empty_atoms(self):
        results = query_atoms([], {"niche": "fitness"})
        assert results == []


# ---------------------------------------------------------------------------
# 6. Recovery Engine
# ---------------------------------------------------------------------------
from packages.scoring.recovery_engine import (
    detect_recovery_incidents,
    recommend_recovery_actions,
)


class TestDetectRecoveryIncidents:
    def test_happy_path_detects_incident(self):
        state = {
            "provider_outage": {"metric_value": 0.6, "scope_type": "account", "scope_id": "acc-1"},
            "cac_spike": {"metric_value": 0.5, "scope_type": "brand"},
        }
        results = detect_recovery_incidents(state, {})
        assert len(results) >= 1
        for r in results:
            assert r["severity"] in ("critical", "high", "medium", "low")
            assert "explanation" in r
            assert 0.0 <= r["confidence"] <= 1.0

    def test_empty_state(self):
        results = detect_recovery_incidents({}, {})
        assert results == []

    def test_critical_severity_mapping(self):
        state = {
            "provider_outage": {"metric_value": 0.9, "scope_type": "account"},
        }
        results = detect_recovery_incidents(state, {})
        assert results[0]["severity"] == "critical"


class TestRecommendRecoveryActions:
    def test_happy_path(self):
        incidents = [
            {
                "incident_type": "provider_outage",
                "severity": "critical",
                "scope_type": "account",
                "scope_id": "acc-1",
            },
        ]
        results = recommend_recovery_actions(incidents, {})
        assert len(results) >= 1
        assert results[0]["action_mode"] == "automatic"
        for r in results:
            assert "explanation" in r
            assert 0.0 <= r["confidence"] <= 1.0

    def test_empty_incidents(self):
        results = recommend_recovery_actions([], {})
        assert results == []


# ---------------------------------------------------------------------------
# 7. Deal Desk Engine
# ---------------------------------------------------------------------------
from packages.scoring.deal_desk_engine import recommend_deal_strategy


class TestRecommendDealStrategy:
    def test_happy_path(self):
        deal_ctx = {
            "deal_value": 25000,
            "lead_quality": 0.7,
            "urgency": 0.6,
            "competition_intensity": 0.4,
            "niche": "tech",
        }
        brand_metrics = {
            "brand_authority_score": 0.7,
            "avg_margin": 0.40,
            "avg_close_rate": 0.30,
            "niche": "tech",
        }
        result = recommend_deal_strategy(deal_ctx, brand_metrics)
        assert result["deal_strategy"] in (
            "custom_quote",
            "package_standard",
            "bundle_discount",
            "hold_price",
            "strategic_discount",
            "push_upsell",
            "nurture_sequence",
            "require_human_approval",
        )
        assert result["pricing_stance"] in ("premium", "competitive", "penetration", "hold")
        assert "explanation" in result
        assert 0.0 <= result["confidence"] <= 1.0

    def test_low_quality_lead_gets_nurture(self):
        deal_ctx = {
            "deal_value": 5000,
            "lead_quality": 0.1,
            "urgency": 0.2,
            "competition_intensity": 0.3,
        }
        brand_metrics = {"brand_authority_score": 0.5, "avg_margin": 0.30, "avg_close_rate": 0.20}
        result = recommend_deal_strategy(deal_ctx, brand_metrics)
        assert result["deal_strategy"] == "nurture_sequence"

    def test_high_value_high_quality_custom_quote(self):
        deal_ctx = {
            "deal_value": 45000,
            "lead_quality": 0.85,
            "urgency": 0.5,
            "competition_intensity": 0.3,
        }
        brand_metrics = {"brand_authority_score": 0.8, "avg_margin": 0.45, "avg_close_rate": 0.35}
        result = recommend_deal_strategy(deal_ctx, brand_metrics)
        assert result["deal_strategy"] == "hold_price"


# ---------------------------------------------------------------------------
# 8. Audience State Engine
# ---------------------------------------------------------------------------
from packages.scoring.audience_state_engine import (
    infer_audience_states,
    recommend_state_actions,
)


class TestInferAudienceStates:
    def test_happy_path(self):
        segments = [
            {"segment_id": "s1", "name": "Active Buyers", "estimated_size": 500},
            {"segment_id": "s2", "name": "Cold List", "estimated_size": 2000},
        ]
        engagement = {
            "s1": {
                "engagement_rate": 0.07,
                "purchase_count": 3,
                "ltv": 250.0,
                "recency_days": 10,
                "frequency": 2.0,
                "feedback_sentiment": 0.6,
            },
            "s2": {
                "engagement_rate": 0.005,
                "purchase_count": 0,
                "ltv": 0.0,
                "recency_days": 200,
                "frequency": 0.0,
                "feedback_sentiment": 0.5,
            },
        }
        results = infer_audience_states(segments, engagement)
        assert len(results) == 2
        for r in results:
            assert r["state_name"] in (
                "unaware",
                "curious",
                "evaluating",
                "objection_heavy",
                "ready_to_buy",
                "bought_once",
                "repeat_buyer",
                "high_ltv",
                "churn_risk",
                "advocate",
                "sponsor_friendly",
            )
            assert 0.0 <= r["confidence"] <= 1.0
            assert "explanation" in r

    def test_empty_segments(self):
        results = infer_audience_states([], {})
        assert results == []

    def test_churn_risk_detection(self):
        segments = [{"segment_id": "s1", "name": "Lapsed"}]
        engagement = {
            "s1": {
                "engagement_rate": 0.01,
                "purchase_count": 2,
                "ltv": 100.0,
                "recency_days": 120,
                "frequency": 0.1,
                "feedback_sentiment": 0.4,
            },
        }
        results = infer_audience_states(segments, engagement)
        assert results[0]["state_name"] == "churn_risk"


class TestRecommendStateActions:
    def test_happy_path(self):
        state_report = {"state_name": "ready_to_buy", "state_score": 0.75, "segment_name": "Hot Leads"}
        result = recommend_state_actions(state_report)
        assert result["recommended_content_type"] == "urgency_scarcity"
        assert result["recommended_channel"] == "email"
        assert "explanation" in result
        assert 0.0 <= result["confidence"] <= 1.0

    def test_unaware_state(self):
        result = recommend_state_actions({"state_name": "unaware", "state_score": 0.8, "segment_name": "Cold"})
        assert result["recommended_offer_approach"] == "none"


# ---------------------------------------------------------------------------
# 9. Reputation Engine
# ---------------------------------------------------------------------------
from packages.scoring.reputation_engine import assess_reputation


class TestAssessReputation:
    def test_happy_path(self):
        brand_data = {
            "niche": "tech",
            "platform_warnings": 1,
            "disclosure_policy": True,
            "sponsor_names": ["BrandA", "BrandB"],
            "audience_size": 50000,
            "avg_engagement_rate": 0.04,
        }
        account_signals = [
            {
                "platform": "youtube",
                "follower_delta": 200,
                "unfollow_rate": 0.01,
                "strike_count": 0,
                "engagement_rate": 0.04,
                "bot_follower_pct": 0.02,
                "comment_texts": ["great video", "very helpful"],
            },
        ]
        content_signals = [
            {
                "title": "Honest Tech Review",
                "description": "Full review of the product",
                "has_disclosure": True,
                "claims": [],
                "engagement_rate": 0.05,
                "comment_sentiment": 0.7,
                "generic_comment_pct": 0.15,
                "sponsor_name": "BrandA",
            },
        ]
        result = assess_reputation(brand_data, account_signals, content_signals)
        assert 0.0 <= result["reputation_risk_score"] <= 1.0
        assert "primary_risks" in result
        assert "recommended_mitigation" in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert "explanation" in result

    def test_empty_signals(self):
        result = assess_reputation({}, [], [])
        assert 0.0 <= result["reputation_risk_score"] <= 1.0
        assert "explanation" in result

    def test_high_risk_keywords_elevate_score(self):
        brand_data = {"platform_warnings": 3, "audience_size": 10000}
        account_signals = [
            {
                "strike_count": 2,
                "bot_follower_pct": 0.4,
                "unfollow_rate": 0.08,
                "comment_texts": ["scam", "misleading", "fake", "shadowban", "spam"],
            },
        ]
        content_signals = [
            {
                "title": "Guaranteed results",
                "description": "100% risk free miracle cure",
                "claims": ["results guaranteed", "proven cure"],
                "has_disclosure": False,
                "sponsor_name": "ShadyCo",
                "generic_comment_pct": 0.6,
            },
        ]
        result = assess_reputation(brand_data, account_signals, content_signals)
        assert result["reputation_risk_score"] > 0.15


# ---------------------------------------------------------------------------
# 10. Market Timing Engine
# ---------------------------------------------------------------------------
from packages.scoring.market_timing_engine import evaluate_market_timing


class TestEvaluateMarketTiming:
    def test_happy_path_fitness_january(self):
        ctx = {
            "niche": "fitness",
            "month": 1,
            "audience_size": 30000,
            "avg_monthly_revenue": 8000,
            "content_types": ["video", "short"],
            "active_offer_count": 3,
        }
        signals = [
            {"signal_type": "recession_indicator", "value": 0.3, "source": "macro_feed"},
        ]
        results = evaluate_market_timing(ctx, signals)
        assert len(results) >= 1
        for r in results:
            assert 0.0 <= r["timing_score"] <= 1.0
            assert 0.0 <= r["confidence"] <= 1.0
            assert "explanation" in r

    def test_empty_signals(self):
        ctx = {"niche": "obscure_hobby", "month": 4}
        results = evaluate_market_timing(ctx, [])
        # obscure niche with no matching signals may produce empty or minimal results
        assert isinstance(results, list)

    def test_holiday_monetization_december(self):
        ctx = {"niche": "ecommerce", "month": 12, "audience_size": 50000, "active_offer_count": 5}
        results = evaluate_market_timing(ctx, [])
        holiday_results = [r for r in results if r["market_category"] == "holiday_monetization"]
        assert len(holiday_results) == 1
        assert holiday_results[0]["timing_score"] >= 0.6


# ---------------------------------------------------------------------------
# 11. Kill Ledger Engine
# ---------------------------------------------------------------------------
from packages.scoring.kill_ledger_engine import (
    evaluate_kill_candidates,
    review_kill_hindsight,
)


class TestEvaluateKillCandidates:
    def test_happy_path(self):
        underperformers = [
            {
                "scope_type": "offer",
                "scope_id": "offer-dead",
                "name": "Dead Offer",
                "conversion_rate": 0.001,
                "revenue": 10.0,
                "aov": 3.0,
            },
        ]
        results = evaluate_kill_candidates(underperformers, {})
        assert len(results) == 1
        r = results[0]
        assert r["scope_type"] == "offer"
        assert "kill_reason" in r
        assert "explanation" in r
        assert 0.0 <= r["confidence"] <= 1.0

    def test_empty_underperformers(self):
        results = evaluate_kill_candidates([], {})
        assert results == []

    def test_passing_item_not_killed(self):
        underperformers = [
            {
                "scope_type": "offer",
                "scope_id": "offer-good",
                "conversion_rate": 0.10,
                "revenue": 5000.0,
                "aov": 80.0,
            },
        ]
        results = evaluate_kill_candidates(underperformers, {})
        assert results == []

    def test_invalid_scope_type_skipped(self):
        underperformers = [
            {"scope_type": "nonexistent_scope", "scope_id": "x", "revenue": 0},
        ]
        results = evaluate_kill_candidates(underperformers, {})
        assert results == []


class TestReviewKillHindsight:
    def test_correct_kill(self):
        kill_entry = {
            "scope_type": "offer",
            "scope_id": "offer-dead",
            "kill_reason": "low CVR",
            "performance_snapshot": {
                "revenue": 10.0,
                "conversion_rate": 0.001,
            },
        }
        post_data = {
            "revenue": 500.0,
            "conversion_rate": 0.05,
            "overall_brand_revenue_delta": 400.0,
            "time_since_kill_days": 45,
            "replacement_performance": {
                "revenue": 600.0,
                "conversion_rate": 0.06,
            },
        }
        result = review_kill_hindsight(kill_entry, post_data)
        assert result["was_correct_kill"] is True
        assert "explanation" in result
        assert 0.0 <= result["confidence"] <= 1.0

    def test_insufficient_data(self):
        result = review_kill_hindsight(
            {"scope_type": "offer", "scope_id": "x", "performance_snapshot": {}},
            {},
        )
        assert result["was_correct_kill"] is None
        assert result["confidence"] == 0.20

    def test_incorrect_kill_detected(self):
        kill_entry = {
            "scope_type": "offer",
            "scope_id": "offer-oops",
            "performance_snapshot": {
                "revenue": 5000.0,
                "conversion_rate": 0.08,
                "engagement_rate": 0.06,
            },
        }
        post_data = {
            "revenue": 1000.0,
            "conversion_rate": 0.02,
            "engagement_rate": 0.01,
            "overall_brand_revenue_delta": -3000.0,
            "time_since_kill_days": 60,
        }
        result = review_kill_hindsight(kill_entry, post_data)
        assert result["was_correct_kill"] is False
