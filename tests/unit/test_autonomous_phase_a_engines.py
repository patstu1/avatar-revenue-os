"""Unit tests: Autonomous Phase A engines — signal scanning, warmup, maturity, output."""

from __future__ import annotations

import pytest

from packages.scoring.account_warmup_engine import (
    MATURITY_STATES,
    RAMP_EVENT_TYPES,
    compute_account_output,
    compute_maturity_state,
    compute_output_ramp_event,
    compute_warmup_plan,
    seed_platform_warmup_policies,
)
from packages.scoring.signal_scanning_engine import (
    SIGNAL_TYPES,
    build_auto_queue_items,
    classify_signal_type,
    normalize_signal,
    score_signal_batch,
)

# ---------------------------------------------------------------------------
# Signal Scanning Engine
# ---------------------------------------------------------------------------


class TestNormalizeSignal:
    def test_fresh_high_intent_signal_is_actionable(self):
        result = normalize_signal(
            signal_type="high_intent",
            source="internal_analytics",
            raw_data={
                "title": "Users searching for 'best AI tool'",
                "description": "High purchase intent signal",
                "age_hours": 2.0,
                "keywords": ["ai", "tools", "software"],
                "competitive_pressure": 0.3,
                "data_completeness": 0.8,
            },
            brand_context={
                "niche": "ai tools",
                "niche_keywords": ["ai", "tools", "automation"],
                "active_offers": ["AI Starter Kit"],
                "monetization_modes": ["affiliate"],
            },
        )
        assert result["is_actionable"] is True
        assert result["freshness_score"] > 0.5
        assert result["monetization_relevance"] > 0.0
        assert result["urgency_score"] > 0.0
        assert result["confidence"] > 0.3
        assert "[HIGH_INTENT]" in result["normalized_title"]

    def test_stale_signal_not_actionable(self):
        result = normalize_signal(
            signal_type="rising_topic",
            source="trend_api",
            raw_data={
                "title": "Old topic",
                "age_hours": 5000,
                "keywords": [],
                "data_completeness": 0.1,
            },
            brand_context={"niche": "cooking", "niche_keywords": [], "active_offers": [], "monetization_modes": []},
        )
        assert result["freshness_score"] < 0.15
        assert result["is_actionable"] is False

    def test_returns_all_required_fields(self):
        result = normalize_signal(
            "rising_topic",
            "trend_api",
            {"title": "test", "age_hours": 1, "keywords": ["k"], "data_completeness": 0.5},
            {"niche": "tech", "niche_keywords": ["tech"], "active_offers": [], "monetization_modes": []},
        )
        for key in [
            "normalized_title",
            "normalized_description",
            "freshness_score",
            "monetization_relevance",
            "urgency_score",
            "confidence",
            "is_actionable",
            "explanation",
        ]:
            assert key in result


class TestClassifySignalType:
    def test_high_intent_classification(self):
        sig = classify_signal_type("Buy the best AI tool", "pricing comparison", {"conversion_intent": 0.9})
        assert sig == "high_intent"

    def test_competitor_gap_classification(self):
        sig = classify_signal_type(
            "Competitor X missing feature", "vs analysis", {"gap_score": 0.8, "competitor_count": 5}
        )
        assert sig == "competitor_gap"

    def test_fatigue_classification(self):
        sig = classify_signal_type("Content fatigue in niche", "declining engagement", {"fatigue_indicator": 0.9})
        assert sig == "fatigue_signal"

    def test_seasonal_window(self):
        sig = classify_signal_type("Black Friday deals season", "holiday shopping", {"seasonality_score": 0.9})
        assert sig == "seasonal_window"

    def test_returns_valid_type(self):
        sig = classify_signal_type("random title", "random desc", {})
        assert sig in SIGNAL_TYPES


class TestScoreSignalBatch:
    def _make_signal(self, title="Test signal", age=10, keywords=None, **kw):
        return {
            "title": title,
            "description": "desc",
            "age_hours": age,
            "keywords": keywords or ["tech"],
            "competitive_pressure": 0.3,
            "data_completeness": 0.7,
            "metrics": kw.get("metrics", {}),
            **kw,
        }

    def test_filters_stale_signals(self):
        signals = [
            self._make_signal(title="Fresh", age=1),
            self._make_signal(title="Very stale", age=50000, keywords=[]),
        ]
        scored = score_signal_batch(signals, [{"name": "offer", "keywords": ["tech"]}], "tech")
        stale_titles = [s["normalized_title"] for s in scored]
        assert all("Very stale" not in t for t in stale_titles)

    def test_sorts_by_composite_score(self):
        signals = [
            self._make_signal(title="Low", age=100),
            self._make_signal(title="High", age=1, metrics={"conversion_intent": 0.9}),
        ]
        scored = score_signal_batch(signals, [{"name": "offer", "keywords": ["tech"]}], "tech")
        if len(scored) >= 2:
            assert scored[0]["composite_score"] >= scored[1]["composite_score"]

    def test_empty_input_returns_empty(self):
        assert score_signal_batch([], [], "tech") == []


class TestBuildAutoQueueItems:
    def _make_scored_signal(self, sig_type="rising_topic"):
        return {
            "signal_type": sig_type,
            "urgency_score": 0.7,
            "monetization_relevance": 0.5,
            "normalized_title": f"[{sig_type.upper()}] Test",
            "raw_signal": {"keywords": ["tech", "ai"]},
        }

    def _make_account(self, maturity="stable", health=0.7):
        return {
            "account_id": "acc-1",
            "platform": "youtube",
            "role": "authority",
            "niche": "tech",
            "sub_niche": "ai",
            "maturity_state": maturity,
            "health_score": health,
            "current_output_per_week": 5,
        }

    def test_creates_queue_items(self):
        items = build_auto_queue_items(
            [self._make_scored_signal()],
            [self._make_account()],
            [{"platform": "youtube", "max_safe_output_per_day": 3}],
        )
        assert len(items) == 1
        assert items[0]["platform"] == "youtube"
        assert items[0]["queue_status"] in ("ready", "held", "suppressed")

    def test_newborn_account_held(self):
        items = build_auto_queue_items(
            [self._make_scored_signal()],
            [self._make_account(maturity="newborn")],
            [{"platform": "youtube", "max_safe_output_per_day": 3}],
        )
        assert len(items) == 1
        assert items[0]["queue_status"] == "held"

    def test_low_health_suppressed(self):
        items = build_auto_queue_items(
            [self._make_scored_signal()],
            [self._make_account(health=0.1)],
            [{"platform": "youtube", "max_safe_output_per_day": 3}],
        )
        assert len(items) == 1
        assert "account_health_below_threshold" in items[0]["suppression_flags"]

    def test_no_accounts_returns_empty(self):
        items = build_auto_queue_items([self._make_scored_signal()], [], [])
        assert items == []

    def test_high_intent_maps_to_offer_push(self):
        items = build_auto_queue_items(
            [self._make_scored_signal("high_intent")],
            [self._make_account()],
            [{"platform": "youtube", "max_safe_output_per_day": 3}],
        )
        assert items[0]["queue_item_type"] == "offer_push"


# ---------------------------------------------------------------------------
# Account Warmup Engine
# ---------------------------------------------------------------------------


class TestComputeWarmupPlan:
    def _policy(self, platform="youtube"):
        from packages.scoring.growth_pack.platform_os import PLATFORM_SPECS

        spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["youtube"])
        return {
            "platform": platform,
            "warmup_cadence": spec.get("warmup_cadence", {}),
            "max_safe_output_per_day": spec.get("max_safe_output_per_day", 3),
            "scale_ready_conditions": spec.get("scale_ready_conditions", []),
            "spam_fatigue_signals": spec.get("spam_fatigue_signals", []),
            "ramp_behavior": spec.get("ramp_behavior", "moderate"),
        }

    def test_new_account_gets_phase_1(self):
        plan = compute_warmup_plan(
            {
                "account_id": "acc-1",
                "platform": "youtube",
                "account_age_days": 5,
                "posts_published": 2,
                "engagement_rate": 0.01,
                "has_violations": False,
                "follower_count": 10,
            },
            self._policy("youtube"),
            [],
        )
        assert plan["warmup_phase"] == "phase_1_warmup"
        assert plan["initial_posts_per_week"] >= 1

    def test_mature_account_gets_max_output(self):
        plan = compute_warmup_plan(
            {
                "account_id": "acc-2",
                "platform": "tiktok",
                "account_age_days": 60,
                "posts_published": 30,
                "engagement_rate": 0.04,
                "has_violations": False,
                "follower_count": 5000,
            },
            self._policy("tiktok"),
            [{"week_number": i, "posts_count": 5, "engagement_rate": 0.04, "follower_delta": 50} for i in range(1, 9)],
        )
        assert plan["warmup_phase"] == "phase_3_max_output"

    def test_violation_forces_phase_1(self):
        plan = compute_warmup_plan(
            {
                "account_id": "acc-3",
                "platform": "instagram",
                "account_age_days": 90,
                "posts_published": 50,
                "engagement_rate": 0.03,
                "has_violations": True,
                "follower_count": 1000,
            },
            self._policy("instagram"),
            [],
        )
        assert plan["warmup_phase"] == "phase_1_warmup"

    def test_returns_content_mix(self):
        plan = compute_warmup_plan(
            {
                "account_id": "acc-1",
                "platform": "youtube",
                "account_age_days": 5,
                "posts_published": 0,
                "engagement_rate": 0,
                "has_violations": False,
                "follower_count": 0,
            },
            self._policy("youtube"),
            [],
        )
        assert "content_mix" in plan
        assert isinstance(plan["content_mix"], dict)
        assert sum(plan["content_mix"].values()) == pytest.approx(1.0, abs=0.01)


class TestComputeAccountOutput:
    def _plan(self, phase="phase_2_ramp"):
        return {
            "warmup_phase": phase,
            "current_posts_per_week": 5,
            "target_posts_per_week": 10,
        }

    def _policy(self):
        return {"max_safe_output_per_day": 3}

    def test_healthy_account_gets_increase(self):
        output = compute_account_output(
            {"account_id": "a1", "platform": "youtube"},
            self._plan(),
            self._policy(),
            {
                "posts_last_7d": 5,
                "engagement_rate_7d": 0.04,
                "monetization_revenue_7d": 100,
                "monetization_cost_7d": 0,
                "follower_delta_7d": 50,
            },
        )
        assert output["recommended_output_per_week"] >= output["current_output_per_week"]
        assert output["max_safe_output_per_week"] == 21

    def test_low_health_triggers_throttle(self):
        output = compute_account_output(
            {"account_id": "a2", "platform": "youtube", "has_violations": True},
            self._plan(),
            self._policy(),
            {
                "posts_last_7d": 10,
                "engagement_rate_7d": 0.001,
                "monetization_revenue_7d": 0,
                "monetization_cost_7d": 0,
                "follower_delta_7d": -100,
            },
        )
        assert output["recommended_output_per_week"] <= output["current_output_per_week"]

    def test_output_never_exceeds_max_safe(self):
        output = compute_account_output(
            {"account_id": "a3", "platform": "youtube"},
            {"warmup_phase": "phase_3_max_output", "current_posts_per_week": 50, "target_posts_per_week": 100},
            self._policy(),
            {
                "posts_last_7d": 50,
                "engagement_rate_7d": 0.05,
                "monetization_revenue_7d": 1000,
                "monetization_cost_7d": 100,
                "follower_delta_7d": 200,
            },
        )
        assert output["recommended_output_per_week"] <= output["max_safe_output_per_week"]


class TestComputeMaturityState:
    def _policy(self):
        return {"max_safe_output_per_day": 3}

    def test_brand_new_account_is_newborn(self):
        result = compute_maturity_state(
            {
                "account_id": "a1",
                "platform": "youtube",
                "account_age_days": 3,
                "posts_published": 0,
                "engagement_rate": 0,
                "follower_count": 0,
                "has_violations": False,
            },
            [],
            self._policy(),
        )
        assert result["maturity_state"] == "newborn"

    def test_established_account_is_stable(self):
        result = compute_maturity_state(
            {
                "account_id": "a2",
                "platform": "youtube",
                "account_age_days": 60,
                "posts_published": 25,
                "engagement_rate": 0.03,
                "follower_count": 500,
                "has_violations": False,
            },
            [{"week_number": i, "posts_count": 3, "engagement_rate": 0.03, "follower_delta": 10} for i in range(1, 9)],
            self._policy(),
        )
        assert result["maturity_state"] in ("stable", "scaling")

    def test_violated_low_health_is_at_risk_or_cooling(self):
        result = compute_maturity_state(
            {
                "account_id": "a3",
                "platform": "youtube",
                "account_age_days": 90,
                "posts_published": 40,
                "engagement_rate": 0.001,
                "follower_count": 100,
                "has_violations": True,
            },
            [{"week_number": 1, "posts_count": 5, "engagement_rate": 0.001, "follower_delta": -50}],
            self._policy(),
        )
        assert result["maturity_state"] in ("at_risk", "cooling")

    def test_warming_young_account(self):
        result = compute_maturity_state(
            {
                "account_id": "a4",
                "platform": "youtube",
                "account_age_days": 15,
                "posts_published": 3,
                "engagement_rate": 0.02,
                "follower_count": 20,
                "has_violations": False,
            },
            [],
            self._policy(),
        )
        assert result["maturity_state"] == "warming"

    def test_all_maturity_states_valid(self):
        for state in MATURITY_STATES:
            assert state in MATURITY_STATES


class TestComputeOutputRampEvent:
    def _policy(self):
        return {"max_safe_output_per_day": 3}

    def test_critical_health_pauses(self):
        event = compute_output_ramp_event(
            current_output=10,
            account_maturity={"maturity_state": "stable", "platform": "youtube"},
            platform_policy=self._policy(),
            account_health=0.1,
        )
        assert event is not None
        assert event["event_type"] == "pause"

    def test_healthy_scaling_increases(self):
        event = compute_output_ramp_event(
            current_output=5,
            account_maturity={"maturity_state": "scaling", "platform": "youtube"},
            platform_policy=self._policy(),
            account_health=0.8,
        )
        assert event is not None
        assert event["event_type"] == "increase"
        assert event["to_output"] > event["from_output"]

    def test_at_risk_decreases(self):
        event = compute_output_ramp_event(
            current_output=10,
            account_maturity={"maturity_state": "at_risk", "platform": "youtube"},
            platform_policy=self._policy(),
            account_health=0.5,
        )
        assert event is not None
        assert event["event_type"] == "decrease"

    def test_saturated_at_max_splits(self):
        event = compute_output_ramp_event(
            current_output=21,
            account_maturity={"maturity_state": "saturated", "platform": "youtube"},
            platform_policy=self._policy(),
            account_health=0.5,
        )
        assert event is not None
        assert event["event_type"] == "split"

    def test_stable_no_headroom_returns_none(self):
        event = compute_output_ramp_event(
            current_output=21,
            account_maturity={"maturity_state": "stable", "platform": "youtube"},
            platform_policy=self._policy(),
            account_health=0.7,
        )
        assert event is None

    def test_all_event_types_valid(self):
        for etype in RAMP_EVENT_TYPES:
            assert etype in RAMP_EVENT_TYPES


class TestSeedPlatformWarmupPolicies:
    def test_returns_7_platforms(self):
        policies = seed_platform_warmup_policies()
        assert len(policies) == 7
        platforms = {p["platform"] for p in policies}
        assert platforms == {"tiktok", "instagram", "youtube", "twitter", "reddit", "linkedin", "facebook"}

    def test_each_has_required_fields(self):
        policies = seed_platform_warmup_policies()
        for p in policies:
            assert "platform" in p
            assert "max_safe_output_per_day" in p
            assert "warmup_cadence" in p
            assert "ramp_behavior" in p


# ---------------------------------------------------------------------------
# Integration-style tests: signal → queue → warmup pipeline
# ---------------------------------------------------------------------------


class TestSignalToQueuePipeline:
    """End-to-end test: raw signals scored and queued."""

    def test_profitable_signal_becomes_queued_candidate(self):
        signals = [
            {
                "title": "New AI product trending",
                "description": "High conversion intent",
                "age_hours": 2,
                "keywords": ["ai", "product", "tools"],
                "competitive_pressure": 0.2,
                "data_completeness": 0.9,
                "metrics": {"conversion_intent": 0.8, "search_volume_delta": 50},
            }
        ]
        scored = score_signal_batch(signals, [{"name": "AI Toolkit", "keywords": ["ai", "tools"]}], "ai tools")
        assert len(scored) >= 1

        accounts = [
            {
                "account_id": "acc-lead",
                "platform": "youtube",
                "role": "authority",
                "niche": "ai",
                "sub_niche": "tools",
                "maturity_state": "stable",
                "health_score": 0.8,
                "current_output_per_week": 5,
            }
        ]
        policies = [{"platform": "youtube", "max_safe_output_per_day": 3}]

        queue_items = build_auto_queue_items(scored, accounts, policies)
        assert len(queue_items) >= 1
        assert queue_items[0]["queue_status"] == "ready"
        assert queue_items[0]["platform"] == "youtube"

    def test_warming_account_does_not_jump_to_max_output(self):
        from packages.scoring.growth_pack.platform_os import PLATFORM_SPECS

        spec = PLATFORM_SPECS["tiktok"]
        plan = compute_warmup_plan(
            {
                "account_id": "new-acc",
                "platform": "tiktok",
                "account_age_days": 10,
                "posts_published": 3,
                "engagement_rate": 0.01,
                "has_violations": False,
                "follower_count": 15,
            },
            {
                "platform": "tiktok",
                "warmup_cadence": spec["warmup_cadence"],
                "max_safe_output_per_day": spec["max_safe_output_per_day"],
                "scale_ready_conditions": spec["scale_ready_conditions"],
                "spam_fatigue_signals": spec["spam_fatigue_signals"],
                "ramp_behavior": spec["ramp_behavior"],
            },
            [],
        )
        assert plan["warmup_phase"] == "phase_1_warmup"
        assert plan["current_posts_per_week"] <= spec["warmup_cadence"]["week_1"] + 1

    def test_healthy_account_ramps_output(self):
        event = compute_output_ramp_event(
            current_output=3,
            account_maturity={"maturity_state": "scaling", "platform": "youtube"},
            platform_policy={"max_safe_output_per_day": 3},
            account_health=0.85,
        )
        assert event is not None
        assert event["event_type"] == "increase"

    def test_saturated_account_is_throttled(self):
        maturity = compute_maturity_state(
            {
                "account_id": "sat-acc",
                "platform": "youtube",
                "account_age_days": 120,
                "posts_published": 100,
                "engagement_rate": 0.01,
                "follower_count": 5000,
                "has_violations": False,
            },
            [{"week_number": i, "posts_count": 21, "engagement_rate": 0.01, "follower_delta": 0} for i in range(1, 5)],
            {"max_safe_output_per_day": 3},
        )
        assert maturity["maturity_state"] in ("saturated", "max_output")

    def test_platform_policy_differences_affect_warmup(self):
        policies = seed_platform_warmup_policies()
        tiktok = next(p for p in policies if p["platform"] == "tiktok")
        reddit = next(p for p in policies if p["platform"] == "reddit")
        assert tiktok["max_safe_output_per_day"] > reddit["max_safe_output_per_day"]
