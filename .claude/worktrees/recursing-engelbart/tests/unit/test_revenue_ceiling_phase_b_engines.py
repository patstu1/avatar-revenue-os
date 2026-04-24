"""Unit tests for Revenue Ceiling Phase B engines."""

import pytest

from packages.scoring.revenue_ceiling_phase_b_engines import (
    build_high_ticket_opportunity,
    build_product_opportunity,
    build_upsell_recommendation,
    compute_revenue_density_row,
    generate_high_ticket_rows,
    generate_product_opportunities,
    generate_upsell_rows,
)


def test_high_ticket_has_required_fields():
    r = build_high_ticket_opportunity("k1", "VIP Coaching Program", "finance", 2000, 500, 0.03)
    for k in (
        "eligibility_score",
        "recommended_offer_path",
        "recommended_cta",
        "expected_close_rate_proxy",
        "expected_deal_value",
        "expected_profit",
        "confidence",
    ):
        assert k in r
    assert r["recommended_offer_path"].get("steps")


def test_high_ticket_rows_from_offers_no_content():
    offers = [{"id": "o1", "name": "Course", "average_order_value": 400, "payout_amount": 80, "conversion_rate": 0.02}]
    rows = generate_high_ticket_rows("x", offers, [])
    assert len(rows) == 1


def test_product_opportunity_fields():
    p = build_product_opportunity("pk", "saas", "founders", 2)
    assert p["product_type"]
    assert p["price_range_max"] >= p["price_range_min"]
    assert p["expected_launch_value"] > 0


def test_generate_product_opportunities_count():
    assert len(generate_product_opportunities("niche", "aud")) == 6


def test_revenue_density_row():
    r = compute_revenue_density_row("cid", "t", 100, 5000, 20, 2000, 0.3)
    assert r["revenue_per_1k_impressions"] == pytest.approx(20.0, rel=0.01)
    assert 0 <= r["ceiling_score"] <= 1


def test_upsell_pair():
    a = {"id": "a", "name": "Low", "epc": 2, "payout_amount": 10, "priority": 1}
    b = {"id": "b", "name": "High", "epc": 5, "payout_amount": 40, "priority": 0}
    r = build_upsell_recommendation("uk", a, b, "email")
    assert r["best_next_offer"]["offer_id"] == "b"
    assert r["best_upsell_sequencing"]


def test_generate_upsell_requires_two_offers():
    assert generate_upsell_rows([{"id": "x", "name": "a", "epc": 1, "payout_amount": 1, "priority": 0}]) == []
    rows = generate_upsell_rows(
        [
            {"id": "a", "name": "A", "epc": 2, "payout_amount": 10, "priority": 2},
            {"id": "b", "name": "B", "epc": 3, "payout_amount": 20, "priority": 1},
        ]
    )
    assert len(rows) == 1
