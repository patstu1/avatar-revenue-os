"""Unit tests for affiliate intelligence engine."""

from packages.scoring.affiliate_intel_engine import (
    build_affiliate_link,
    detect_blockers,
    detect_leaks,
    rank_offer,
    rank_offers,
    select_best_offer,
)


class TestRanking:
    def test_high_epc_ranks_high(self):
        score = rank_offer(
            {
                "epc": 4.0,
                "conversion_rate": 0.05,
                "commission_rate": 30,
                "trust_score": 0.8,
                "content_fit_score": 0.7,
                "platform_fit_score": 0.7,
                "audience_fit_score": 0.7,
            }
        )
        assert score > 0.5

    def test_zero_offer(self):
        score = rank_offer({})
        assert 0 <= score <= 1

    def test_rank_orders(self):
        offers = [
            {"id": "a", "epc": 4.0, "conversion_rate": 0.05, "commission_rate": 30, "trust_score": 0.8},
            {"id": "b", "epc": 0.5, "conversion_rate": 0.01, "commission_rate": 5, "trust_score": 0.3},
        ]
        ranked = rank_offers(offers)
        assert ranked[0]["id"] == "a"

    def test_select_best(self):
        offers = [
            {"id": "a", "epc": 4.0, "platform_fit_score": 0.8},
            {"id": "b", "epc": 1.0, "platform_fit_score": 0.2},
        ]
        best = select_best_offer(offers, platform="tiktok")
        assert best["id"] == "a"


class TestLinkBuilder:
    def test_builds_utm(self):
        link = build_affiliate_link(
            {"affiliate_url": "https://example.com/offer?ref=abc"},
            content_item_id="ci123",
            campaign_id="camp456",
            platform="tiktok",
        )
        assert "utm_source=tiktok" in link["full_url"]
        assert "utm_medium=affiliate" in link["full_url"]
        assert link["disclosure_applied"] is False

    def test_empty_url(self):
        link = build_affiliate_link({})
        assert link["full_url"] == ""


class TestLeakDetection:
    def test_high_clicks_no_conversion(self):
        leaks = detect_leaks([], [{"id": "l1", "offer_id": "o1", "click_count": 100, "conversion_count": 0}])
        assert any(l["leak_type"] == "high_clicks_zero_conversions" for l in leaks)

    def test_very_low_conversion(self):
        leaks = detect_leaks([], [{"id": "l1", "offer_id": "o1", "click_count": 500, "conversion_count": 1}])
        assert any(l["leak_type"] == "very_low_conversion" for l in leaks)

    def test_blocked_offer_active(self):
        leaks = detect_leaks([{"id": "o1", "is_active": True, "blocker_state": "blocked", "refund_rate": 0}], [])
        assert any(l["leak_type"] == "blocked_offer_still_active" for l in leaks)

    def test_high_refund(self):
        leaks = detect_leaks(
            [{"id": "o1", "is_active": True, "blocker_state": None, "refund_rate": 0.25, "epc": 2.0}], []
        )
        assert any(l["leak_type"] == "high_refund_rate" for l in leaks)

    def test_no_leaks_clean(self):
        leaks = detect_leaks(
            [{"id": "o1", "is_active": True, "blocker_state": None, "refund_rate": 0.02}],
            [{"id": "l1", "offer_id": "o1", "click_count": 10, "conversion_count": 2}],
        )
        assert len(leaks) == 0


class TestBlockerDetection:
    def test_no_url(self):
        blockers = detect_blockers(
            [
                {
                    "id": "o1",
                    "product_name": "Test",
                    "affiliate_url": None,
                    "destination_url": None,
                    "epc": 1.0,
                    "commission_rate": 10,
                }
            ]
        )
        assert any(b["blocker_type"] == "no_destination_url" for b in blockers)

    def test_no_commission(self):
        blockers = detect_blockers(
            [{"id": "o1", "product_name": "Test", "affiliate_url": "https://x.com", "epc": 0, "commission_rate": 0}]
        )
        assert any(b["blocker_type"] == "no_commission_data" for b in blockers)
