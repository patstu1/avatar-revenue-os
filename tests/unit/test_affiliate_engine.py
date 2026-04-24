"""Unit tests — affiliate link engine, placement engine, product selection."""
from __future__ import annotations


def test_generate_tracking_id():
    from packages.scoring.affiliate_link_engine import generate_tracking_id
    tid = generate_tracking_id("content-123", "acct-456", "youtube")
    assert len(tid) == 12
    assert tid == generate_tracking_id("content-123", "acct-456", "youtube")
    tid2 = generate_tracking_id("content-789", "acct-456", "youtube")
    assert tid != tid2


def test_select_best_product_finance():
    from packages.scoring.affiliate_link_engine import select_best_product
    product = select_best_product("personal_finance", "How to budget", "tid123")
    assert product["name"]
    assert product["payout"] > 0


def test_select_best_product_tech():
    from packages.scoring.affiliate_link_engine import select_best_product
    product = select_best_product("tech_reviews", "Best laptop 2026", "tid456")
    assert product["name"]


def test_select_best_product_unknown_niche():
    from packages.scoring.affiliate_link_engine import select_best_product
    product = select_best_product("underwater_basket_weaving", "", "tid")
    assert product["name"]


def test_get_all_products():
    from packages.scoring.affiliate_link_engine import get_all_products_for_niche
    products = get_all_products_for_niche("health_fitness")
    assert len(products) >= 2
    payouts = [p["payout"] for p in products]
    assert payouts == sorted(payouts, reverse=True)


def test_build_clickbank_link():
    import os
    os.environ["CLICKBANK_CLERK_ID"] = "testaff"
    from packages.scoring.affiliate_link_engine import build_clickbank_link
    link = build_clickbank_link("vendor1", "track123")
    assert "testaff" in link
    assert "vendor1" in link
    assert "track123" in link
    del os.environ["CLICKBANK_CLERK_ID"]


def test_build_amazon_link():
    import os
    os.environ["AMAZON_ASSOCIATES_TAG"] = "mystore-20"
    from packages.scoring.affiliate_link_engine import build_amazon_link
    link = build_amazon_link("B08N5WRWNW", "track456")
    assert "mystore-20" in link
    assert "B08N5WRWNW" in link
    del os.environ["AMAZON_ASSOCIATES_TAG"]


def test_build_semrush_link():
    import os
    os.environ["SEMRUSH_AFFILIATE_KEY"] = "myref"
    from packages.scoring.affiliate_link_engine import build_semrush_link
    link = build_semrush_link("track789", "spring2026")
    assert "myref" in link
    assert "track789" in link
    del os.environ["SEMRUSH_AFFILIATE_KEY"]


# ── Placement Engine ──

def test_select_placement_youtube():
    from packages.scoring.affiliate_placement_engine import select_placement
    placement = select_placement("youtube")
    assert placement["placement_id"] in ["description_top", "in_caption", "pinned_comment", "end_card"]


def test_select_placement_tiktok():
    from packages.scoring.affiliate_placement_engine import select_placement
    placement = select_placement("tiktok")
    assert placement["placement_id"] in ["link_in_bio", "in_caption", "pinned_comment"]


def test_build_placement_instruction():
    from packages.scoring.affiliate_placement_engine import build_placement_instruction
    instr = build_placement_instruction({"placement_id": "link_in_bio"}, "https://example.com", "Product X")
    assert "bio" in instr.lower()
    assert "Product X" in instr


def test_build_placement_pinned_comment():
    from packages.scoring.affiliate_placement_engine import build_placement_instruction
    instr = build_placement_instruction({"placement_id": "pinned_comment"}, "https://example.com", "Tool Y")
    assert "comment" in instr.lower()
    assert "Tool Y" in instr


def test_placement_experiment_variants():
    from packages.scoring.affiliate_placement_engine import get_placement_for_experiment
    variants = get_placement_for_experiment("youtube")
    assert len(variants) >= 3
    ids = [v.get("variant_name") or v.get("id") for v in variants]
    assert "description_top" in ids


def test_niche_products_cover_all_major_niches():
    from packages.scoring.affiliate_link_engine import NICHE_TOP_PRODUCTS
    major = ["personal_finance", "make_money_online", "health_fitness", "tech_reviews", "ai_tools", "beauty_skincare", "software_saas"]
    for niche in major:
        assert niche in NICHE_TOP_PRODUCTS, f"Missing products for {niche}"
        assert len(NICHE_TOP_PRODUCTS[niche]) >= 2, f"Too few products for {niche}"
