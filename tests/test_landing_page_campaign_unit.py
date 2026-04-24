"""Unit tests for landing page + campaign engines."""
from packages.scoring.campaign_engine import CAMPAIGN_TYPES, construct_campaign, construct_variant, detect_blockers
from packages.scoring.landing_page_engine import PAGE_TYPES, generate_page, generate_variant, score_page_quality


class TestLandingPageEngine:
    def test_all_page_types(self):
        assert len(PAGE_TYPES) == 11
        for pt in ("product", "review", "comparison", "advertorial", "presell", "optin", "lead_magnet", "quiz_funnel", "authority", "creator_revenue", "sponsor"):
            assert pt in PAGE_TYPES

    def test_generate_page(self):
        page = generate_page({"name": "Test Offer", "monetization_method": "affiliate"}, page_type="product")
        assert page["page_type"] == "product"
        assert page["headline"]
        assert page["truth_label"] == "recommendation_only"
        assert len(page["cta_blocks"]) >= 1
        assert len(page["disclosure_blocks"]) >= 1

    def test_generate_variant(self):
        page = generate_page({"name": "Test"}, page_type="review")
        v = generate_variant(page, 1)
        assert v["variant_label"]
        assert v["headline"]

    def test_score_quality_pass(self):
        page = generate_page({"name": "Good", "monetization_method": "affiliate"}, page_type="product")
        score = score_page_quality(page, objection_count=3, offer_cvr=0.05)
        assert score["verdict"] in ("pass", "warn")
        assert score["total_score"] > 0

    def test_score_quality_empty(self):
        score = score_page_quality({})
        assert score["verdict"] in ("fail", "warn")

    def test_each_type_generates(self):
        for pt in PAGE_TYPES:
            page = generate_page({"name": f"Test {pt}"}, page_type=pt)
            assert page["page_type"] == pt
            assert page["headline"]


class TestCampaignEngine:
    def test_all_campaign_types(self):
        assert len(CAMPAIGN_TYPES) == 8
        for ct in ("affiliate", "lead_gen", "product_conversion", "creator_revenue", "sponsor", "newsletter_growth", "authority_building", "experiment"):
            assert ct in CAMPAIGN_TYPES

    def test_construct_campaign(self):
        camp = construct_campaign({"name": "Offer A", "monetization_method": "affiliate", "epc": 2.0, "conversion_rate": 0.04}, {"niche": "tech"}, [{"id": "a1", "platform": "tiktok"}], campaign_type="affiliate")
        assert camp["campaign_type"] == "affiliate"
        assert camp["campaign_name"]
        assert camp["truth_label"] == "recommendation_only"
        assert camp["expected_upside"] > 0

    def test_construct_variant(self):
        camp = construct_campaign({"name": "A"}, {"niche": "tech"}, [], campaign_type="lead_gen")
        v = construct_variant(camp, 0)
        assert v["variant_label"]
        assert v["is_control"] is True

    def test_detect_blockers_no_accounts(self):
        camp = {"target_accounts": [], "campaign_type": "affiliate"}
        blockers = detect_blockers(camp, {})
        assert any(b["blocker_type"] == "no_accounts" for b in blockers)

    def test_detect_blockers_no_landing_page(self):
        camp = {"target_accounts": ["a1"], "campaign_type": "affiliate", "landing_page_id": None}
        blockers = detect_blockers(camp, {})
        assert any(b["blocker_type"] == "no_landing_page" for b in blockers)

    def test_no_blocker_for_authority(self):
        camp = {"target_accounts": ["a1"], "campaign_type": "authority_building", "landing_page_id": None, "monetization_path": "organic"}
        blockers = detect_blockers(camp, {})
        assert not any(b["blocker_type"] == "no_landing_page" for b in blockers)

    def test_suppressed_hook_blocker(self):
        camp = {"target_accounts": ["a1"], "hook_family": "curiosity", "campaign_type": "affiliate", "landing_page_id": "lp1", "monetization_path": "affiliate"}
        blockers = detect_blockers(camp, {"suppressed_families": ["curiosity"]})
        assert any(b["blocker_type"] == "suppressed_hook" for b in blockers)
