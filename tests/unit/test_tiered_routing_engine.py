"""Unit tests for Tiered Routing Engine."""

from packages.scoring.tiered_routing_engine import (
    CONTENT_TYPES,
    COST_PER_UNIT,
    QUALITY_TIERS,
    ROUTING_TABLE,
    check_budget_remaining,
    classify_task_tier,
    compute_monthly_projection,
    estimate_cost,
    route_content_task,
    route_to_provider,
)


def test_routing_table_covers_all_combinations():
    for ct in CONTENT_TYPES:
        for tier in QUALITY_TIERS:
            assert (ct, tier) in ROUTING_TABLE, f"Missing ({ct}, {tier})"


def test_hero_text_routes_to_claude():
    assert route_to_provider("text", "hero") == "claude"


def test_standard_text_routes_to_gemini():
    assert route_to_provider("text", "standard") == "gemini_flash"


def test_bulk_text_routes_to_deepseek():
    assert route_to_provider("text", "bulk") == "deepseek"


def test_hero_image_routes_to_gpt_image():
    assert route_to_provider("image", "hero") == "gpt_image"


def test_bulk_image_routes_to_imagen4():
    assert route_to_provider("image", "bulk") == "imagen4"


def test_hero_video_routes_to_higgsfield():
    assert route_to_provider("video", "hero") == "higgsfield"


def test_bulk_video_routes_to_wan():
    assert route_to_provider("video", "bulk") == "wan"


def test_avatar_routes_by_tier():
    assert route_to_provider("avatar", "hero") == "heygen"
    assert route_to_provider("avatar", "standard") == "did"
    assert route_to_provider("avatar", "bulk") == "synthesia"


def test_hero_voice_routes_to_elevenlabs():
    assert route_to_provider("voice", "hero") == "elevenlabs"


def test_standard_voice_routes_to_fish_audio():
    assert route_to_provider("voice", "standard") == "fish_audio"


def test_bulk_voice_routes_to_voxtral():
    assert route_to_provider("voice", "bulk") == "voxtral"


def test_music_routes_by_tier():
    assert route_to_provider("music", "hero") == "suno"
    assert route_to_provider("music", "standard") == "mubert"
    assert route_to_provider("music", "bulk") == "stable_audio"


def test_classify_promoted_always_hero():
    assert classify_task_tier("instagram", is_promoted=True) == "hero"


def test_classify_x_defaults_bulk():
    assert classify_task_tier("x") == "bulk"


def test_classify_blog_defaults_hero():
    assert classify_task_tier("blog") == "hero"


def test_classify_tiktok_defaults_standard():
    assert classify_task_tier("tiktok") == "standard"


def test_estimate_cost_positive():
    for provider in COST_PER_UNIT:
        assert estimate_cost(provider) >= 0


def test_estimate_cost_scales_with_units():
    c1 = estimate_cost("claude", 1)
    c10 = estimate_cost("claude", 10)
    assert c10 > c1


def test_budget_within():
    r = check_budget_remaining(15.0, 5.0)
    assert r["within_budget"] is True
    assert r["remaining_usd"] == 10.0


def test_budget_exceeded():
    r = check_budget_remaining(15.0, 20.0)
    assert r["within_budget"] is False


def test_monthly_projection_returns_total():
    p = compute_monthly_projection(300)
    assert p["total_estimated_usd"] > 0
    assert p["cost_per_post_usd"] > 0
    assert "by_provider" in p


def test_route_content_task_returns_all_fields():
    r = route_content_task("Write a product review", "instagram", "text")
    for k in ("content_type", "quality_tier", "routed_provider", "estimated_cost", "explanation"):
        assert k in r


def test_hero_is_more_expensive_than_bulk():
    hero = route_content_task("ad creative", "blog", "text", is_promoted=True)
    bulk = route_content_task("hashtags", "x", "text")
    assert hero["estimated_cost"] >= bulk["estimated_cost"]
