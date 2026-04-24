"""Unit tests for offer lab engine."""
import pytest
from packages.scoring.offer_lab_engine import (
    OFFER_TYPES, VARIANT_TYPES, generate_offer, generate_variants,
    generate_pricing_test, generate_positioning_test, generate_bundles,
    generate_upsells, score_offer, detect_offer_issues, recommend_revision,
)


class TestGeneration:
    def test_generate_offer(self):
        o = generate_offer({"name": "Test Product", "monetization_method": "affiliate", "payout_amount": 30, "epc": 2.0, "conversion_rate": 0.04}, {"niche": "tech"})
        assert o["offer_name"] == "Test Product"
        assert o["truth_label"] == "recommendation_only"
        assert o["expected_upside"] > 0

    def test_generate_variants(self):
        o = generate_offer({"name": "Test", "payout_amount": 50}, {})
        variants = generate_variants(o)
        assert len(variants) == 8
        types = {v["variant_type"] for v in variants}
        assert "budget" in types and "premium" in types
        assert variants[0]["is_control"] is True

    def test_pricing_test(self):
        pt = generate_pricing_test({"price_point": 100})
        assert pt["test_price"] < pt["control_price"]

    def test_positioning_test(self):
        pos = generate_positioning_test({"primary_angle": "value_demo"})
        assert pos["test_angle"] != pos["control_angle"]


class TestBundlesUpsells:
    def test_bundles(self):
        offers = [{"id": "a", "offer_name": "A", "price_point": 30}, {"id": "b", "offer_name": "B", "price_point": 50}]
        bundles = generate_bundles(offers)
        assert len(bundles) == 1
        assert bundles[0]["savings_pct"] == 15.0

    def test_no_bundle_single(self):
        assert generate_bundles([{"id": "a"}]) == []

    def test_upsells(self):
        offers = [{"id": "a", "price_point": 10}, {"id": "b", "price_point": 50}]
        upsells = generate_upsells(offers)
        assert len(upsells) == 1
        assert upsells[0]["upsell_type"] == "upsell"


class TestScoring:
    def test_high_score(self):
        s = score_offer({"expected_upside": 80, "confidence": 0.9, "platform_fit": 0.8, "margin_estimate": 40, "trust_requirement": "low"})
        assert s > 0.5

    def test_low_score(self):
        s = score_offer({"expected_upside": 0, "confidence": 0.1, "platform_fit": 0.2, "margin_estimate": 0, "trust_requirement": "high"})
        assert s < 0.4


class TestIssues:
    def test_no_upside(self):
        issues = detect_offer_issues({"expected_upside": 0, "price_point": 10, "confidence": 0.5})
        assert any(i["blocker_type"] == "no_expected_upside" for i in issues)

    def test_low_confidence(self):
        issues = detect_offer_issues({"expected_upside": 50, "price_point": 10, "confidence": 0.1})
        assert any(i["blocker_type"] == "low_confidence" for i in issues)

    def test_clean_offer(self):
        issues = detect_offer_issues({"expected_upside": 50, "price_point": 30, "confidence": 0.7, "trust_requirement": "medium", "platform_fit": 0.6})
        assert len(issues) == 0


class TestRevision:
    def test_revision_recs(self):
        issues = [{"blocker_type": "no_expected_upside"}]
        recs = recommend_revision({}, issues)
        assert "revise_pricing" in recs

    def test_keep_current(self):
        recs = recommend_revision({"expected_upside": 80, "confidence": 0.9, "platform_fit": 0.8, "margin_estimate": 40, "trust_requirement": "low"}, [])
        assert "keep_current" in recs


class TestTypes:
    def test_offer_types(self):
        assert len(OFFER_TYPES) == 10
    def test_variant_types(self):
        assert len(VARIANT_TYPES) == 8
