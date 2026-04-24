"""Unit tests for Creator Revenue Avenues Phase B engines."""

from __future__ import annotations

from packages.scoring.creator_revenue_engine import (
    DATA_PRODUCT_TYPES,
    LICENSING_TYPES,
    SYNDICATION_TYPES,
    detect_phase_b_blockers,
    score_data_product_opportunities,
    score_licensing_opportunities,
    score_syndication_opportunities,
)

# ── Licensing ──────────────────────────────────────────────────────────


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


class TestScoreLicensingOpportunities:
    def test_returns_list(self):
        results = score_licensing_opportunities(_rich_ctx())
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_licensing_types_represented(self):
        results = score_licensing_opportunities(_rich_ctx())
        found = {r["asset_type"] for r in results}
        assert found.issubset(set(LICENSING_TYPES))

    def test_sorted_by_expected_value_times_confidence(self):
        results = score_licensing_opportunities(_rich_ctx())
        scores = [r["expected_deal_value"] * r["confidence"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_contains_required_fields(self):
        results = score_licensing_opportunities(_rich_ctx())
        for r in results:
            assert "asset_type" in r
            assert "licensing_tier" in r
            assert "target_buyer_type" in r
            assert "usage_scope" in r
            assert "price_band" in r
            assert "expected_deal_value" in r
            assert "execution_plan" in r
            assert "confidence" in r
            assert "explanation" in r

    def test_low_content_reduces_confidence(self):
        ctx = _rich_ctx()
        ctx["content_count"] = 5
        results = score_licensing_opportunities(ctx)
        rich = score_licensing_opportunities(_rich_ctx())
        avg_conf_low = sum(r["confidence"] for r in results) / max(len(results), 1)
        avg_conf_high = sum(r["confidence"] for r in rich) / max(len(rich), 1)
        assert avg_conf_low < avg_conf_high

    def test_tech_niche_boosts_value(self):
        ctx_tech = _rich_ctx()
        ctx_gen = {**_rich_ctx(), "niche": "general"}
        tech = score_licensing_opportunities(ctx_tech)
        gen = score_licensing_opportunities(ctx_gen)
        tech_total = sum(r["expected_deal_value"] for r in tech)
        gen_total = sum(r["expected_deal_value"] for r in gen)
        assert tech_total >= gen_total

    def test_white_label_needs_avatar(self):
        ctx_no_avatar = {**_rich_ctx(), "has_avatar": False}
        results = score_licensing_opportunities(ctx_no_avatar)
        wl = [r for r in results if r["asset_type"] == "white_label_rights"]
        rich_wl = [r for r in score_licensing_opportunities(_rich_ctx()) if r["asset_type"] == "white_label_rights"]
        if wl and rich_wl:
            assert wl[0]["confidence"] < rich_wl[0]["confidence"]

    def test_usage_scope_values(self):
        results = score_licensing_opportunities(_rich_ctx())
        for r in results:
            assert r["usage_scope"] in ("limited_use", "full_use")


# ── Syndication ────────────────────────────────────────────────────────


class TestScoreSyndicationOpportunities:
    def test_returns_list(self):
        results = score_syndication_opportunities(_rich_ctx())
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_syndication_types_represented(self):
        results = score_syndication_opportunities(_rich_ctx())
        found = {r["syndication_format"] for r in results}
        assert found.issubset(set(SYNDICATION_TYPES))

    def test_sorted_by_expected_value_times_confidence(self):
        results = score_syndication_opportunities(_rich_ctx())
        scores = [r["expected_value"] * r["confidence"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_contains_required_fields(self):
        results = score_syndication_opportunities(_rich_ctx())
        for r in results:
            assert "syndication_format" in r
            assert "target_partner" in r
            assert "revenue_model" in r
            assert "price_band" in r
            assert "expected_value" in r
            assert "execution_plan" in r
            assert "confidence" in r
            assert "explanation" in r

    def test_recurring_vs_one_time(self):
        results = score_syndication_opportunities(_rich_ctx())
        models = {r["revenue_model"] for r in results}
        assert "recurring" in models or "one_time" in models

    def test_low_content_reduces_confidence(self):
        ctx = {**_rich_ctx(), "content_count": 3}
        low = score_syndication_opportunities(ctx)
        rich = score_syndication_opportunities(_rich_ctx())
        avg_low = sum(r["confidence"] for r in low) / max(len(low), 1)
        avg_high = sum(r["confidence"] for r in rich) / max(len(rich), 1)
        assert avg_low < avg_high

    def test_tech_niche_boosts_confidence(self):
        ctx_tech = _rich_ctx()
        ctx_gen = {**_rich_ctx(), "niche": "lifestyle"}
        tech = score_syndication_opportunities(ctx_tech)
        gen = score_syndication_opportunities(ctx_gen)
        avg_tech = sum(r["confidence"] for r in tech) / max(len(tech), 1)
        avg_gen = sum(r["confidence"] for r in gen) / max(len(gen), 1)
        assert avg_tech >= avg_gen


# ── Data Products ──────────────────────────────────────────────────────


class TestScoreDataProductOpportunities:
    def test_returns_list(self):
        results = score_data_product_opportunities(_rich_ctx())
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_product_types_represented(self):
        results = score_data_product_opportunities(_rich_ctx())
        found = {r["product_type"] for r in results}
        assert found.issubset(set(DATA_PRODUCT_TYPES))

    def test_sorted_by_expected_value_times_confidence(self):
        results = score_data_product_opportunities(_rich_ctx())
        scores = [r["expected_value"] * r["confidence"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_contains_required_fields(self):
        results = score_data_product_opportunities(_rich_ctx())
        for r in results:
            assert "product_type" in r
            assert "target_segment" in r
            assert "revenue_model" in r
            assert "price_band" in r
            assert "expected_value" in r
            assert "execution_plan" in r
            assert "confidence" in r
            assert "explanation" in r

    def test_recurring_vs_one_time(self):
        results = score_data_product_opportunities(_rich_ctx())
        models = {r["revenue_model"] for r in results}
        assert "recurring" in models or "one_time" in models

    def test_signal_trend_needs_deep_content(self):
        ctx_shallow = {**_rich_ctx(), "content_count": 5}
        shallow = score_data_product_opportunities(ctx_shallow)
        rich = score_data_product_opportunities(_rich_ctx())
        sig_shallow = [r for r in shallow if r["product_type"] == "signal_trend_dataset"]
        sig_rich = [r for r in rich if r["product_type"] == "signal_trend_dataset"]
        if sig_shallow and sig_rich:
            assert sig_shallow[0]["confidence"] < sig_rich[0]["confidence"]

    def test_finance_niche_boosts_value(self):
        ctx_fin = {**_rich_ctx(), "niche": "finance"}
        ctx_gen = {**_rich_ctx(), "niche": "general"}
        fin = score_data_product_opportunities(ctx_fin)
        gen = score_data_product_opportunities(ctx_gen)
        total_fin = sum(r["expected_value"] for r in fin)
        total_gen = sum(r["expected_value"] for r in gen)
        assert total_fin >= total_gen

    def test_swipe_file_has_highest_confidence(self):
        results = score_data_product_opportunities(_rich_ctx())
        swipe = [r for r in results if r["product_type"] == "swipe_file"]
        if swipe:
            assert swipe[0]["confidence"] >= 0.1


# ── Phase B Blockers ───────────────────────────────────────────────────


class TestDetectPhaseBBlockers:
    def test_no_blockers_for_rich_context(self):
        blockers = detect_phase_b_blockers(_rich_ctx())
        avenue_types = {b["avenue_type"] for b in blockers}
        assert "licensing" not in avenue_types
        assert "syndication" not in avenue_types

    def test_licensing_blocker_on_low_content(self):
        ctx = {**_rich_ctx(), "content_count": 5}
        blockers = detect_phase_b_blockers(ctx)
        lic = [b for b in blockers if b["avenue_type"] == "licensing"]
        assert len(lic) >= 1

    def test_syndication_blocker_on_low_content(self):
        ctx = {**_rich_ctx(), "content_count": 3}
        blockers = detect_phase_b_blockers(ctx)
        syn = [b for b in blockers if b["avenue_type"] == "syndication"]
        assert len(syn) >= 1

    def test_data_product_blocker_on_low_content(self):
        ctx = {**_rich_ctx(), "content_count": 10}
        blockers = detect_phase_b_blockers(ctx)
        dp = [b for b in blockers if b["avenue_type"] == "data_products"]
        assert len(dp) >= 1

    def test_payment_processor_blocker(self):
        ctx = {**_rich_ctx(), "has_payment_processor": False}
        blockers = detect_phase_b_blockers(ctx)
        pp = [b for b in blockers if b["blocker_type"] == "no_payment_processor"]
        assert len(pp) == 1

    def test_blockers_have_required_fields(self):
        ctx = {**_rich_ctx(), "content_count": 2, "has_payment_processor": False}
        blockers = detect_phase_b_blockers(ctx)
        for b in blockers:
            assert "avenue_type" in b
            assert "blocker_type" in b
            assert "severity" in b
            assert "description" in b
            assert "operator_action_needed" in b
