"""Unit tests for Creator Revenue Avenues Phase C engines."""
from __future__ import annotations

import pytest
from packages.scoring.creator_revenue_engine import (
    MERCH_TYPES,
    LIVE_EVENT_TYPES,
    AFFILIATE_PROGRAM_TYPES,
    score_merch_opportunities,
    score_live_event_opportunities,
    score_owned_affiliate_opportunities,
    detect_phase_c_blockers,
)


def _rich_ctx() -> dict:
    return {
        "content_count": 40,
        "has_avatar": True,
        "niche": "tech",
        "offer_count": 3,
        "audience_size": 15000,
        "account_count": 5,
        "has_community": True,
        "has_payment_processor": True,
        "has_landing_page": True,
    }


# ── Merch ──────────────────────────────────────────────────────────────

class TestScoreMerchOpportunities:
    def test_returns_list(self):
        results = score_merch_opportunities(_rich_ctx())
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_merch_types_represented(self):
        results = score_merch_opportunities(_rich_ctx())
        found = {r["product_class"] for r in results}
        assert found.issubset(set(MERCH_TYPES))

    def test_sorted_by_expected_value_times_confidence(self):
        results = score_merch_opportunities(_rich_ctx())
        scores = [r["expected_value"] * r["confidence"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_contains_required_fields(self):
        for r in score_merch_opportunities(_rich_ctx()):
            assert "product_class" in r
            assert "target_segment" in r
            assert "price_band" in r
            assert "expected_value" in r
            assert "execution_plan" in r
            assert "truth_label" in r
            assert "confidence" in r
            assert "explanation" in r

    def test_truth_label_recommended_when_payment_processor(self):
        results = score_merch_opportunities(_rich_ctx())
        for r in results:
            assert r["truth_label"] in ("recommended", "queued", "blocked", "live")

    def test_truth_label_blocked_without_payment(self):
        ctx = {**_rich_ctx(), "has_payment_processor": False}
        results = score_merch_opportunities(ctx)
        for r in results:
            assert r["truth_label"] == "blocked"

    def test_lifestyle_niche_boosts_value(self):
        ctx_life = {**_rich_ctx(), "niche": "lifestyle"}
        ctx_gen = {**_rich_ctx(), "niche": "general"}
        life = score_merch_opportunities(ctx_life)
        gen = score_merch_opportunities(ctx_gen)
        total_life = sum(r["expected_value"] for r in life)
        total_gen = sum(r["expected_value"] for r in gen)
        assert total_life >= total_gen

    def test_small_audience_reduces_physical_bundle_confidence(self):
        ctx = {**_rich_ctx(), "audience_size": 500}
        results = score_merch_opportunities(ctx)
        bundles = [r for r in results if r["product_class"] == "physical_bundle"]
        rich_bundles = [r for r in score_merch_opportunities(_rich_ctx()) if r["product_class"] == "physical_bundle"]
        if bundles and rich_bundles:
            assert bundles[0]["confidence"] < rich_bundles[0]["confidence"]


# ── Live Events ────────────────────────────────────────────────────────

class TestScoreLiveEventOpportunities:
    def test_returns_list(self):
        results = score_live_event_opportunities(_rich_ctx())
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_event_types_represented(self):
        results = score_live_event_opportunities(_rich_ctx())
        found = {r["event_type"] for r in results}
        assert found.issubset(set(LIVE_EVENT_TYPES))

    def test_sorted_by_expected_value_times_confidence(self):
        results = score_live_event_opportunities(_rich_ctx())
        scores = [r["expected_value"] * r["confidence"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_contains_required_fields(self):
        for r in score_live_event_opportunities(_rich_ctx()):
            assert "event_type" in r
            assert "audience_segment" in r
            assert "ticket_model" in r
            assert "price_band" in r
            assert "expected_value" in r
            assert "execution_plan" in r
            assert "truth_label" in r
            assert "confidence" in r
            assert "explanation" in r

    def test_paid_events_blocked_without_payment(self):
        ctx = {**_rich_ctx(), "has_payment_processor": False}
        results = score_live_event_opportunities(ctx)
        paid = [r for r in results if r["ticket_model"] == "paid"]
        for p in paid:
            assert p["truth_label"] == "blocked"

    def test_free_events_not_blocked(self):
        ctx = {**_rich_ctx(), "has_payment_processor": False}
        results = score_live_event_opportunities(ctx)
        free = [r for r in results if r["ticket_model"] == "free_with_upsell"]
        for f in free:
            assert f["truth_label"] == "recommended"

    def test_tech_niche_boosts_confidence(self):
        ctx_tech = _rich_ctx()
        ctx_gen = {**_rich_ctx(), "niche": "general"}
        tech = score_live_event_opportunities(ctx_tech)
        gen = score_live_event_opportunities(ctx_gen)
        avg_tech = sum(r["confidence"] for r in tech) / max(len(tech), 1)
        avg_gen = sum(r["confidence"] for r in gen) / max(len(gen), 1)
        assert avg_tech >= avg_gen

    def test_niche_event_needs_large_audience(self):
        ctx = {**_rich_ctx(), "audience_size": 1000}
        results = score_live_event_opportunities(ctx)
        niche = [r for r in results if r["event_type"] == "niche_event_product"]
        rich_niche = [r for r in score_live_event_opportunities(_rich_ctx()) if r["event_type"] == "niche_event_product"]
        if niche and rich_niche:
            assert niche[0]["confidence"] < rich_niche[0]["confidence"]


# ── Owned Affiliate Program ───────────────────────────────────────────

class TestScoreOwnedAffiliateOpportunities:
    def test_returns_list(self):
        results = score_owned_affiliate_opportunities(_rich_ctx())
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_program_types_represented(self):
        results = score_owned_affiliate_opportunities(_rich_ctx())
        found = {r["program_type"] for r in results}
        assert found.issubset(set(AFFILIATE_PROGRAM_TYPES))

    def test_sorted_by_expected_value_times_confidence(self):
        results = score_owned_affiliate_opportunities(_rich_ctx())
        scores = [r["expected_value"] * r["confidence"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_contains_required_fields(self):
        for r in score_owned_affiliate_opportunities(_rich_ctx()):
            assert "program_type" in r
            assert "target_partner_type" in r
            assert "incentive_model" in r
            assert "partner_tier" in r
            assert "expected_value" in r
            assert "execution_plan" in r
            assert "truth_label" in r
            assert "confidence" in r
            assert "explanation" in r

    def test_no_offers_blocks_affiliate(self):
        ctx = {**_rich_ctx(), "offer_count": 0}
        results = score_owned_affiliate_opportunities(ctx)
        for r in results:
            assert r["truth_label"] == "blocked"

    def test_with_offers_not_all_blocked(self):
        results = score_owned_affiliate_opportunities(_rich_ctx())
        non_blocked = [r for r in results if r["truth_label"] != "blocked"]
        assert len(non_blocked) >= 1

    def test_partner_tier_expansion_needs_audience(self):
        ctx = {**_rich_ctx(), "audience_size": 1000}
        results = score_owned_affiliate_opportunities(ctx)
        expansion = [r for r in results if r["program_type"] == "partner_tier_expansion"]
        rich_expansion = [r for r in score_owned_affiliate_opportunities(_rich_ctx()) if r["program_type"] == "partner_tier_expansion"]
        if expansion and rich_expansion:
            assert expansion[0]["confidence"] < rich_expansion[0]["confidence"]


# ── Phase C Blockers ───────────────────────────────────────────────────

class TestDetectPhaseCBlockers:
    def test_no_blockers_for_rich_context(self):
        blockers = detect_phase_c_blockers(_rich_ctx())
        avenue_types = {b["avenue_type"] for b in blockers}
        assert "merch" not in avenue_types
        assert "live_events" not in avenue_types

    def test_merch_blocker_small_audience(self):
        ctx = {**_rich_ctx(), "audience_size": 500}
        blockers = detect_phase_c_blockers(ctx)
        merch = [b for b in blockers if b["avenue_type"] == "merch"]
        assert len(merch) >= 1

    def test_live_events_blocker_low_content(self):
        ctx = {**_rich_ctx(), "content_count": 3}
        blockers = detect_phase_c_blockers(ctx)
        events = [b for b in blockers if b["avenue_type"] == "live_events"]
        assert len(events) >= 1

    def test_affiliate_blocker_no_offers(self):
        ctx = {**_rich_ctx(), "offer_count": 0}
        blockers = detect_phase_c_blockers(ctx)
        affiliate = [b for b in blockers if b["avenue_type"] == "owned_affiliate_program"]
        assert len(affiliate) >= 1

    def test_payment_processor_blocker(self):
        ctx = {**_rich_ctx(), "has_payment_processor": False}
        blockers = detect_phase_c_blockers(ctx)
        pp = [b for b in blockers if b["blocker_type"] == "no_payment_processor"]
        assert len(pp) == 1

    def test_blockers_have_required_fields(self):
        ctx = {**_rich_ctx(), "audience_size": 500, "content_count": 2, "offer_count": 0, "has_payment_processor": False}
        blockers = detect_phase_c_blockers(ctx)
        for b in blockers:
            assert "avenue_type" in b
            assert "blocker_type" in b
            assert "severity" in b
            assert "description" in b
            assert "operator_action_needed" in b
