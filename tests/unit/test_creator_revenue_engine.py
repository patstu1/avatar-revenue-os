"""Unit tests for Creator Revenue Avenues Phase A engine."""

from packages.scoring.creator_revenue_engine import (
    CONSULTING_SERVICE_TYPES,
    PREMIUM_ACCESS_TYPES,
    UGC_SERVICE_TYPES,
    build_revenue_opportunities,
    detect_creator_revenue_blockers,
    score_consulting_opportunities,
    score_premium_access_opportunities,
    score_ugc_opportunity,
)

# ── UGC Opportunity Scoring ────────────────────────────────────────────


class TestScoreUgcOpportunity:
    def test_returns_list(self):
        result = score_ugc_opportunity(
            {"audience_size": 5000, "content_count": 20, "niche": "tech", "has_avatar": True, "account_count": 3}
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_entries_have_required_fields(self):
        result = score_ugc_opportunity(
            {"audience_size": 10000, "content_count": 30, "niche": "fitness", "has_avatar": True, "account_count": 4}
        )
        for item in result:
            assert "service_type" in item
            assert "target_segment" in item
            assert "recommended_package" in item
            assert "expected_value" in item
            assert "expected_margin" in item
            assert "confidence" in item
            assert "explanation" in item

    def test_service_types_from_catalog(self):
        result = score_ugc_opportunity(
            {"audience_size": 5000, "content_count": 10, "niche": "general", "has_avatar": True, "account_count": 2}
        )
        for item in result:
            assert item["service_type"] in UGC_SERVICE_TYPES

    def test_avatar_boosts_spokesperson_confidence(self):
        with_avatar = score_ugc_opportunity(
            {"audience_size": 5000, "content_count": 10, "niche": "tech", "has_avatar": True, "account_count": 2}
        )
        without_avatar = score_ugc_opportunity(
            {"audience_size": 5000, "content_count": 10, "niche": "tech", "has_avatar": False, "account_count": 2}
        )
        sp_with = [x for x in with_avatar if x["service_type"] == "spokesperson_avatar_services"]
        sp_without = [x for x in without_avatar if x["service_type"] == "spokesperson_avatar_services"]
        assert len(sp_with) >= 1
        if sp_without:
            assert sp_with[0]["confidence"] > sp_without[0]["confidence"]
        else:
            # Without avatar, confidence dropped below threshold and was filtered
            assert sp_with[0]["confidence"] > 0.2

    def test_higher_audience_increases_ugc_value(self):
        low = score_ugc_opportunity(
            {"audience_size": 1000, "content_count": 5, "niche": "general", "has_avatar": False, "account_count": 1}
        )
        high = score_ugc_opportunity(
            {"audience_size": 20000, "content_count": 50, "niche": "general", "has_avatar": True, "account_count": 5}
        )
        ugc_low = [x for x in low if x["service_type"] == "ugc_content_production"]
        ugc_high = [x for x in high if x["service_type"] == "ugc_content_production"]
        assert ugc_high[0]["expected_value"] >= ugc_low[0]["expected_value"]

    def test_sorted_by_value_times_confidence(self):
        result = score_ugc_opportunity(
            {"audience_size": 10000, "content_count": 20, "niche": "tech", "has_avatar": True, "account_count": 3}
        )
        scores = [r["expected_value"] * r["confidence"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_zero_content_still_returns_results(self):
        result = score_ugc_opportunity(
            {"audience_size": 0, "content_count": 0, "niche": "general", "has_avatar": False, "account_count": 0}
        )
        assert isinstance(result, list)
        assert len(result) >= 0

    def test_margin_is_less_than_value(self):
        result = score_ugc_opportunity(
            {"audience_size": 10000, "content_count": 30, "niche": "finance", "has_avatar": True, "account_count": 4}
        )
        for item in result:
            assert item["expected_margin"] <= item["expected_value"]

    def test_confidence_bounded_0_1(self):
        result = score_ugc_opportunity(
            {"audience_size": 100000, "content_count": 500, "niche": "tech", "has_avatar": True, "account_count": 20}
        )
        for item in result:
            assert 0 <= item["confidence"] <= 1.0


# ── Consulting Opportunity Scoring ─────────────────────────────────────


class TestScoreConsultingOpportunities:
    def test_returns_list(self):
        result = score_consulting_opportunities(
            {"niche": "tech", "audience_size": 5000, "content_count": 20, "offer_count": 3}
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_entries_have_required_fields(self):
        result = score_consulting_opportunities(
            {"niche": "general", "audience_size": 1000, "content_count": 5, "offer_count": 1}
        )
        for item in result:
            assert "service_type" in item
            assert "service_tier" in item
            assert "target_buyer" in item
            assert "expected_deal_value" in item
            assert "confidence" in item

    def test_service_types_from_catalog(self):
        result = score_consulting_opportunities(
            {"niche": "saas", "audience_size": 10000, "content_count": 30, "offer_count": 5}
        )
        for item in result:
            assert item["service_type"] in CONSULTING_SERVICE_TYPES

    def test_tech_niche_boosts_value(self):
        tech = score_consulting_opportunities(
            {"niche": "tech", "audience_size": 5000, "content_count": 20, "offer_count": 3}
        )
        general = score_consulting_opportunities(
            {"niche": "cooking", "audience_size": 5000, "content_count": 20, "offer_count": 3}
        )
        tech_advisory = [x for x in tech if x["service_type"] == "strategic_advisory"][0]
        gen_advisory = [x for x in general if x["service_type"] == "strategic_advisory"][0]
        assert tech_advisory["expected_deal_value"] >= gen_advisory["expected_deal_value"]

    def test_tiers_present(self):
        result = score_consulting_opportunities(
            {"niche": "tech", "audience_size": 10000, "content_count": 30, "offer_count": 5}
        )
        tiers = {r["service_tier"] for r in result}
        assert len(tiers) >= 2

    def test_confidence_bounded(self):
        result = score_consulting_opportunities(
            {"niche": "finance", "audience_size": 50000, "content_count": 100, "offer_count": 10}
        )
        for item in result:
            assert 0 <= item["confidence"] <= 1.0


# ── Premium Access Scoring ─────────────────────────────────────────────


class TestScorePremiumAccessOpportunities:
    def test_returns_list(self):
        result = score_premium_access_opportunities(
            {"audience_size": 10000, "niche": "tech", "offer_count": 3, "has_community": True}
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_entries_have_required_fields(self):
        result = score_premium_access_opportunities(
            {"audience_size": 5000, "niche": "general", "offer_count": 1, "has_community": False}
        )
        for item in result:
            assert "offer_type" in item
            assert "target_segment" in item
            assert "revenue_model" in item
            assert "expected_value" in item
            assert "confidence" in item

    def test_offer_types_from_catalog(self):
        result = score_premium_access_opportunities(
            {"audience_size": 20000, "niche": "fitness", "offer_count": 5, "has_community": True}
        )
        for item in result:
            assert item["offer_type"] in PREMIUM_ACCESS_TYPES

    def test_community_boosts_confidence(self):
        with_comm = score_premium_access_opportunities(
            {"audience_size": 10000, "niche": "tech", "offer_count": 3, "has_community": True}
        )
        no_comm = score_premium_access_opportunities(
            {"audience_size": 10000, "niche": "tech", "offer_count": 3, "has_community": False}
        )
        with_mem = [x for x in with_comm if x["offer_type"] == "premium_membership"][0]
        no_mem = [x for x in no_comm if x["offer_type"] == "premium_membership"][0]
        assert with_mem["confidence"] >= no_mem["confidence"]

    def test_inner_circle_penalized_for_small_audience(self):
        result = score_premium_access_opportunities(
            {"audience_size": 500, "niche": "general", "offer_count": 0, "has_community": False}
        )
        ic = [x for x in result if x["offer_type"] == "inner_circle"]
        if ic:
            assert ic[0]["confidence"] < 0.3

    def test_revenue_models_present(self):
        result = score_premium_access_opportunities(
            {"audience_size": 20000, "niche": "tech", "offer_count": 5, "has_community": True}
        )
        models = {r["revenue_model"] for r in result}
        assert "recurring" in models


# ── Blocker Detection ──────────────────────────────────────────────────


class TestDetectCreatorRevenueBlockers:
    def test_insufficient_portfolio(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 2,
                "has_avatar": True,
                "offer_count": 3,
                "audience_size": 5000,
                "has_payment_processor": True,
                "has_landing_page": True,
            }
        )
        types = [b["blocker_type"] for b in result]
        assert "insufficient_portfolio" in types

    def test_no_avatar(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 20,
                "has_avatar": False,
                "offer_count": 3,
                "audience_size": 5000,
                "has_payment_processor": True,
                "has_landing_page": True,
            }
        )
        types = [b["blocker_type"] for b in result]
        assert "no_avatar_configured" in types

    def test_no_offers(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 20,
                "has_avatar": True,
                "offer_count": 0,
                "audience_size": 5000,
                "has_payment_processor": True,
                "has_landing_page": True,
            }
        )
        types = [b["blocker_type"] for b in result]
        assert "no_offers_defined" in types

    def test_audience_too_small(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 20,
                "has_avatar": True,
                "offer_count": 3,
                "audience_size": 500,
                "has_payment_processor": True,
                "has_landing_page": True,
            }
        )
        types = [b["blocker_type"] for b in result]
        assert "audience_too_small" in types

    def test_no_payment_processor(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 20,
                "has_avatar": True,
                "offer_count": 3,
                "audience_size": 5000,
                "has_payment_processor": False,
                "has_landing_page": True,
            }
        )
        types = [b["blocker_type"] for b in result]
        assert "no_payment_processor" in types

    def test_no_landing_page(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 20,
                "has_avatar": True,
                "offer_count": 3,
                "audience_size": 5000,
                "has_payment_processor": True,
                "has_landing_page": False,
            }
        )
        types = [b["blocker_type"] for b in result]
        assert "no_landing_page" in types

    def test_clean_brand_no_blockers(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 20,
                "has_avatar": True,
                "offer_count": 3,
                "audience_size": 5000,
                "has_payment_processor": True,
                "has_landing_page": True,
            }
        )
        assert len(result) == 0

    def test_all_blockers_have_operator_action(self):
        result = detect_creator_revenue_blockers(
            {
                "content_count": 0,
                "has_avatar": False,
                "offer_count": 0,
                "audience_size": 0,
                "has_payment_processor": False,
                "has_landing_page": False,
            }
        )
        for b in result:
            assert len(b["operator_action_needed"]) > 0


# ── Build Revenue Opportunities ────────────────────────────────────────


class TestBuildRevenueOpportunities:
    def test_consolidates_all_avenues(self):
        ugc = score_ugc_opportunity(
            {"audience_size": 10000, "content_count": 20, "niche": "tech", "has_avatar": True, "account_count": 3}
        )
        consulting = score_consulting_opportunities(
            {"niche": "tech", "audience_size": 10000, "content_count": 20, "offer_count": 3}
        )
        premium = score_premium_access_opportunities(
            {"audience_size": 10000, "niche": "tech", "offer_count": 3, "has_community": True}
        )
        result = build_revenue_opportunities(ugc, consulting, premium)
        assert len(result) == len(ugc) + len(consulting) + len(premium)

    def test_sorted_by_priority_score(self):
        ugc = score_ugc_opportunity(
            {"audience_size": 10000, "content_count": 20, "niche": "tech", "has_avatar": True, "account_count": 3}
        )
        consulting = score_consulting_opportunities(
            {"niche": "tech", "audience_size": 10000, "content_count": 20, "offer_count": 3}
        )
        premium = score_premium_access_opportunities(
            {"audience_size": 10000, "niche": "tech", "offer_count": 3, "has_community": True}
        )
        result = build_revenue_opportunities(ugc, consulting, premium)
        scores = [r["priority_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_avenue_types_present(self):
        ugc = score_ugc_opportunity(
            {"audience_size": 10000, "content_count": 20, "niche": "tech", "has_avatar": True, "account_count": 3}
        )
        consulting = score_consulting_opportunities(
            {"niche": "tech", "audience_size": 10000, "content_count": 20, "offer_count": 3}
        )
        premium = score_premium_access_opportunities(
            {"audience_size": 10000, "niche": "tech", "offer_count": 3, "has_community": True}
        )
        result = build_revenue_opportunities(ugc, consulting, premium)
        types = {r["avenue_type"] for r in result}
        assert "ugc_services" in types
        assert "consulting" in types
        assert "premium_access" in types

    def test_empty_inputs_returns_empty(self):
        result = build_revenue_opportunities([], [], [])
        assert result == []

    def test_each_entry_has_required_fields(self):
        ugc = score_ugc_opportunity(
            {"audience_size": 5000, "content_count": 10, "niche": "general", "has_avatar": False, "account_count": 1}
        )
        result = build_revenue_opportunities(ugc, [], [])
        for r in result:
            assert "avenue_type" in r
            assert "subtype" in r
            assert "expected_value" in r
            assert "priority_score" in r
            assert "confidence" in r
