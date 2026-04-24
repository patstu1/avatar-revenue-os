"""Unit tests for Autonomous Phase B scoring engines."""

from packages.scoring.execution_policy_engine import (
    ACTION_TYPES,
    EXECUTION_MODES,
    KILL_SWITCH_CLASSES,
    MONETIZATION_ROUTES,
    ROUTE_CLASSES,
    RUN_STATUSES,
    RUN_STEPS,
    SUPPRESSION_TYPES,
    compute_execution_policy,
    compute_policies_for_brand,
    evaluate_suppressions,
    plan_distribution,
    select_monetization_route,
)

# ---------------------------------------------------------------------------
# Execution Policy Engine
# ---------------------------------------------------------------------------

class TestComputeExecutionPolicy:
    def test_high_confidence_low_risk_is_autonomous(self):
        result = compute_execution_policy(
            "create_content_brief", 0.9, 0.8,
            {"default_mode": "autonomous", "compliance_level": "standard",
             "budget_remaining": 1000, "platform_sensitivity": "standard",
             "has_active_violations": False},
        )
        assert result["execution_mode"] == "autonomous"
        assert result["approval_requirement"] == "none"

    def test_low_confidence_becomes_manual(self):
        result = compute_execution_policy(
            "split_account", 0.2, 0.3,
            {"default_mode": "guarded", "compliance_level": "strict",
             "budget_remaining": 10, "platform_sensitivity": "high",
             "has_active_violations": True},
        )
        assert result["execution_mode"] == "manual"
        assert result["approval_requirement"] == "operator_required"

    def test_default_mode_overrides_autonomous(self):
        result = compute_execution_policy(
            "send_notification", 0.95, 0.9,
            {"default_mode": "manual", "compliance_level": "standard",
             "budget_remaining": 1000, "platform_sensitivity": "standard",
             "has_active_violations": False},
        )
        assert result["execution_mode"] == "manual"

    def test_violations_increase_risk(self):
        no_viol = compute_execution_policy(
            "publish_content", 0.7, 0.6,
            {"default_mode": "autonomous", "compliance_level": "standard",
             "budget_remaining": 1000, "platform_sensitivity": "standard",
             "has_active_violations": False},
        )
        with_viol = compute_execution_policy(
            "publish_content", 0.7, 0.6,
            {"default_mode": "autonomous", "compliance_level": "standard",
             "budget_remaining": 1000, "platform_sensitivity": "standard",
             "has_active_violations": True},
        )
        assert with_viol["risk_score"] > no_viol["risk_score"]

    def test_returns_all_required_fields(self):
        result = compute_execution_policy(
            "select_monetization", 0.6, 0.5,
            {"default_mode": "guarded"},
        )
        for key in ["action_type", "execution_mode", "approval_requirement",
                     "rollback_rule", "kill_switch_class", "explanation"]:
            assert key in result

    def test_mode_always_valid(self):
        result = compute_execution_policy(
            "trigger_follow_up", 0.5, 0.5, {},
        )
        assert result["execution_mode"] in EXECUTION_MODES

    def test_kill_switch_always_valid(self):
        result = compute_execution_policy(
            "pause_account", 0.3, 0.2, {},
        )
        assert result["kill_switch_class"] in KILL_SWITCH_CLASSES

    def test_high_risk_actions_get_review(self):
        result = compute_execution_policy(
            "split_account", 0.8, 0.8,
            {"default_mode": "autonomous"},
        )
        assert result["approval_requirement"] in ("operator_review", "operator_required")


class TestComputePoliciesForBrand:
    def test_returns_policy_per_action_type(self):
        results = compute_policies_for_brand(
            ACTION_TYPES, {at: 0.6 for at in ACTION_TYPES}, 0.5, {},
        )
        assert len(results) == len(ACTION_TYPES)

    def test_all_policies_have_mode(self):
        results = compute_policies_for_brand(
            ["publish_content", "suppress_lane"], {"publish_content": 0.9, "suppress_lane": 0.3}, 0.5, {},
        )
        for r in results:
            assert r["execution_mode"] in EXECUTION_MODES


# ---------------------------------------------------------------------------
# Monetization Route Selection
# ---------------------------------------------------------------------------

class TestSelectMonetizationRoute:
    def test_selects_valid_route(self):
        result = select_monetization_route(
            {"content_family": "review_comparison", "niche": "tech", "signal_type": "affiliate_opportunity",
             "monetization_path_hint": "affiliate", "urgency": 0.7},
            [{"name": "Tech Course", "type": "digital_product", "keywords": ["tech"], "revenue_per_conversion": 100, "active": True}],
            {"conversion_intent": 0.6, "engagement_rate": 0.03, "email_list_size": 500,
             "community_size": 200, "follower_count": 10000},
            {"platform": "youtube", "maturity_state": "stable", "health_score": 0.7},
        )
        assert result["selected_route"] in MONETIZATION_ROUTES

    def test_returns_all_required_fields(self):
        result = select_monetization_route(
            {"content_family": "general"}, [], {},
            {"platform": "tiktok", "maturity_state": "warming", "health_score": 0.5},
        )
        for key in ["selected_route", "route_class", "funnel_path",
                     "follow_up_requirements", "confidence", "explanation"]:
            assert key in result

    def test_route_class_is_valid(self):
        result = select_monetization_route(
            {"content_family": "conversion_content", "monetization_path_hint": "owned_product"},
            [{"name": "P", "type": "course", "keywords": [], "revenue_per_conversion": 200, "active": True}],
            {"conversion_intent": 0.8}, {"platform": "youtube", "maturity_state": "stable", "health_score": 0.8},
        )
        assert result["route_class"] in ROUTE_CLASSES

    def test_low_health_reduces_confidence(self):
        healthy = select_monetization_route(
            {"content_family": "general"}, [], {"conversion_intent": 0.5},
            {"platform": "youtube", "maturity_state": "stable", "health_score": 0.9},
        )
        unhealthy = select_monetization_route(
            {"content_family": "general"}, [], {"conversion_intent": 0.5},
            {"platform": "youtube", "maturity_state": "at_risk", "health_score": 0.2},
        )
        assert unhealthy["confidence"] <= healthy["confidence"]

    def test_hint_boosts_matching_route(self):
        result = select_monetization_route(
            {"content_family": "general", "monetization_path_hint": "sponsors"},
            [{"name": "S", "type": "sponsor", "keywords": [], "revenue_per_conversion": 500, "active": True}],
            {"conversion_intent": 0.4, "follower_count": 10000},
            {"platform": "youtube", "maturity_state": "stable", "health_score": 0.7},
        )
        assert result["selected_route"] == "sponsors"

    def test_all_18_routes_covered(self):
        assert len(MONETIZATION_ROUTES) == 18


# ---------------------------------------------------------------------------
# Suppression Evaluation
# ---------------------------------------------------------------------------

class TestEvaluateSuppressions:
    def test_low_health_triggers_pause(self):
        results = evaluate_suppressions(
            [{"account_id": "a1", "health_score": 0.15, "saturation_score": 0.3,
              "maturity_state": "stable", "current_output_per_week": 7}],
            [], {},
        )
        types = [s["suppression_type"] for s in results]
        assert "pause_lane" in types

    def test_high_saturation_triggers_reduce(self):
        results = evaluate_suppressions(
            [{"account_id": "a2", "health_score": 0.6, "saturation_score": 0.85,
              "maturity_state": "stable", "current_output_per_week": 10}],
            [], {},
        )
        types = [s["suppression_type"] for s in results]
        assert "reduce_output" in types

    def test_at_risk_blocks_expansion(self):
        results = evaluate_suppressions(
            [{"account_id": "a3", "health_score": 0.5, "saturation_score": 0.3,
              "maturity_state": "at_risk", "current_output_per_week": 5}],
            [], {},
        )
        types = [s["suppression_type"] for s in results]
        assert "suppress_account_expansion" in types

    def test_healthy_account_no_suppression(self):
        results = evaluate_suppressions(
            [{"account_id": "a4", "health_score": 0.8, "saturation_score": 0.2,
              "maturity_state": "scaling", "current_output_per_week": 5}],
            [], {},
        )
        assert len(results) == 0

    def test_weak_content_family_suppressed(self):
        results = evaluate_suppressions(
            [],
            [{"id": "q1", "content_family": "creative_refresh", "platform": "youtube",
              "priority_score": 0.1, "monetization_path": "none", "queue_status": "ready"}],
            {"content_fatigue_score": 0.8},
        )
        types = [s["suppression_type"] for s in results]
        assert "suppress_content_family" in types

    def test_all_suppression_types_valid(self):
        results = evaluate_suppressions(
            [{"account_id": "a5", "health_score": 0.1, "saturation_score": 0.9,
              "maturity_state": "at_risk", "current_output_per_week": 14}],
            [{"id": "q2", "content_family": "test", "platform": "x",
              "priority_score": 0.05, "monetization_path": "none", "queue_status": "ready"}],
            {"content_fatigue_score": 0.9, "revenue_trend": "down",
             "overall_engagement_rate": 0.01},
        )
        for s in results:
            assert s["suppression_type"] in SUPPRESSION_TYPES

    def test_suppression_has_required_fields(self):
        results = evaluate_suppressions(
            [{"account_id": "a6", "health_score": 0.1, "saturation_score": 0.5,
              "maturity_state": "stable", "current_output_per_week": 10}],
            [], {},
        )
        for s in results:
            for key in ["suppression_type", "affected_scope", "trigger_reason",
                         "confidence", "explanation"]:
                assert key in s


# ---------------------------------------------------------------------------
# Distribution Planning
# ---------------------------------------------------------------------------

class TestPlanDistribution:
    def test_creates_distribution_for_other_platforms(self):
        result = plan_distribution(
            source_concept="10 AI tools review",
            source_platform="youtube",
            content_family="review_comparison",
            available_accounts=[
                {"account_id": "a1", "platform": "youtube", "maturity_state": "stable",
                 "health_score": 0.8, "current_output_per_week": 5, "max_safe_output_per_week": 14},
                {"account_id": "a2", "platform": "tiktok", "maturity_state": "scaling",
                 "health_score": 0.7, "current_output_per_week": 10, "max_safe_output_per_week": 28},
                {"account_id": "a3", "platform": "linkedin", "maturity_state": "stable",
                 "health_score": 0.6, "current_output_per_week": 3, "max_safe_output_per_week": 7},
            ],
            platform_policies=[
                {"platform": "tiktok", "max_safe_output_per_day": 4},
                {"platform": "linkedin", "max_safe_output_per_day": 1},
            ],
        )
        platforms = [t["platform"] for t in result["target_platforms"]]
        assert "youtube" not in platforms
        assert "tiktok" in platforms or "linkedin" in platforms

    def test_excludes_unhealthy_accounts(self):
        result = plan_distribution(
            "Test concept", "youtube", "general",
            [{"account_id": "a1", "platform": "tiktok", "maturity_state": "at_risk",
              "health_score": 0.2, "current_output_per_week": 3, "max_safe_output_per_week": 21}],
            [],
        )
        assert len(result["target_platforms"]) == 0

    def test_returns_required_fields(self):
        result = plan_distribution("Test", "youtube", "general", [], [])
        for key in ["source_concept", "target_platforms", "derivative_types",
                     "cadence", "publish_timing", "duplication_guard",
                     "confidence", "explanation"]:
            assert key in result

    def test_staggered_cadence(self):
        result = plan_distribution(
            "Concept", "youtube", "general",
            [
                {"account_id": "a1", "platform": "tiktok", "maturity_state": "stable",
                 "health_score": 0.7, "current_output_per_week": 5, "max_safe_output_per_week": 21},
                {"account_id": "a2", "platform": "instagram", "maturity_state": "stable",
                 "health_score": 0.7, "current_output_per_week": 3, "max_safe_output_per_week": 14},
            ],
            [{"platform": "tiktok", "max_safe_output_per_day": 3},
             {"platform": "instagram", "max_safe_output_per_day": 2}],
        )
        if len(result["cadence"]) >= 2:
            delays = [v["delay_hours_from_source"] for v in result["cadence"].values()]
            assert delays[0] < delays[1]

    def test_no_duplicate_platforms(self):
        result = plan_distribution(
            "Concept", "youtube", "general",
            [
                {"account_id": "a1", "platform": "tiktok", "maturity_state": "stable",
                 "health_score": 0.7, "current_output_per_week": 5, "max_safe_output_per_week": 21},
                {"account_id": "a2", "platform": "tiktok", "maturity_state": "scaling",
                 "health_score": 0.8, "current_output_per_week": 10, "max_safe_output_per_week": 28},
            ],
            [],
        )
        platforms = [t["platform"] for t in result["target_platforms"]]
        assert len(platforms) == len(set(platforms))


# ---------------------------------------------------------------------------
# Integration-style pipeline tests
# ---------------------------------------------------------------------------

class TestPhaseBPipeline:
    def test_queued_post_through_policy_to_mode(self):
        """Queue item → execution policy → valid mode."""
        policy = compute_execution_policy(
            "publish_content", 0.75, 0.7,
            {"default_mode": "autonomous"},
        )
        assert policy["execution_mode"] in EXECUTION_MODES
        assert policy["action_type"] == "publish_content"

    def test_approved_run_creates_distribution_plan(self):
        """Running run → distribution plan with targets."""
        plan = plan_distribution(
            "AI Avatar tutorial", "youtube", "authority_piece",
            [{"account_id": "a1", "platform": "tiktok", "maturity_state": "stable",
              "health_score": 0.7, "current_output_per_week": 5, "max_safe_output_per_week": 21}],
            [{"platform": "tiktok", "max_safe_output_per_day": 3}],
        )
        assert len(plan["target_platforms"]) > 0
        assert plan["confidence"] > 0

    def test_monetization_route_selected_automatically(self):
        """Content context → monetization route with funnel."""
        result = select_monetization_route(
            {"content_family": "conversion_content", "monetization_path_hint": "owned_product"},
            [{"name": "Course", "type": "course", "keywords": ["ai"], "revenue_per_conversion": 297, "active": True}],
            {"conversion_intent": 0.7, "engagement_rate": 0.04, "email_list_size": 1000,
             "community_size": 500, "follower_count": 20000},
            {"platform": "youtube", "maturity_state": "scaling", "health_score": 0.85},
        )
        assert result["selected_route"] in MONETIZATION_ROUTES
        assert result["funnel_path"] is not None
        assert len(result["follow_up_requirements"]) > 0

    def test_weak_lane_creates_suppression(self):
        """Low health account → suppression execution."""
        results = evaluate_suppressions(
            [{"account_id": "weak1", "health_score": 0.15, "saturation_score": 0.4,
              "maturity_state": "at_risk", "current_output_per_week": 8}],
            [], {},
        )
        assert len(results) > 0
        assert any(s["suppression_type"] == "pause_lane" for s in results)

    def test_run_steps_are_ordered(self):
        """RUN_STEPS is a valid ordered pipeline."""
        assert RUN_STEPS[0] == "queued"
        assert RUN_STEPS[-1] == "completed"
        assert "policy_check" in RUN_STEPS
        assert "distribution_planning" in RUN_STEPS
        assert "monetization_routing" in RUN_STEPS
        assert "publishing" in RUN_STEPS

    def test_run_statuses_are_valid(self):
        for s in RUN_STATUSES:
            assert s in ("pending", "running", "paused", "completed", "failed", "cancelled")
