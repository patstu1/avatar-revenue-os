"""Tiered Routing Engine — route content tasks to the cheapest adequate provider.

TEXT:   hero -> claude,  standard -> gemini_flash,  bulk -> deepseek
IMAGE:  hero -> gpt_image,  standard -> imagen4,  bulk -> imagen4
VIDEO:  hero -> runway,  standard -> kling,  bulk -> kling
AVATAR: hero -> heygen,  standard -> heygen,  bulk -> heygen
VOICE:  hero -> elevenlabs,  standard -> fish_audio,  bulk -> voxtral
MUSIC:  all tiers -> suno
"""
from __future__ import annotations
from typing import Any

QUALITY_TIERS = ["hero", "standard", "bulk"]

CONTENT_TYPES = ["text", "image", "video", "avatar", "voice", "music"]

ROUTING_TABLE: dict[tuple[str, str], str] = {
    ("text", "hero"): "claude",
    ("text", "standard"): "gemini_flash",
    ("text", "bulk"): "deepseek",
    ("image", "hero"): "gpt_image",
    ("image", "standard"): "flux",
    ("image", "bulk"): "imagen4",
    ("video", "hero"): "higgsfield",
    ("video", "premium"): "runway",
    ("video", "standard"): "kling",
    ("video", "bulk"): "wan",
    ("avatar", "hero"): "heygen",
    ("avatar", "standard"): "did",
    ("avatar", "bulk"): "synthesia",
    ("voice", "hero"): "elevenlabs",
    ("voice", "standard"): "fish_audio",
    ("voice", "bulk"): "voxtral",
    ("music", "hero"): "suno",
    ("music", "standard"): "mubert",
    ("music", "bulk"): "stable_audio",
}

TYPE_DEFAULTS: dict[str, str] = {
    "text": "gemini_flash",
    "image": "imagen4",
    "video": "kling",
    "avatar": "did",
    "voice": "fish_audio",
    "music": "suno",
}

COST_PER_UNIT: dict[str, float] = {
    "claude": 0.018,
    "gemini_flash": 0.003,
    "deepseek": 0.0004,
    "gpt_image": 0.04,
    "imagen4": 0.02,
    "flux": 0.055,
    "kling": 0.35,
    "runway": 0.50,
    "heygen": 0.50,
    "elevenlabs": 0.03,
    "fish_audio": 0.015,
    "voxtral": 0.016,
    "suno": 0.10,
    "did": 0.25,
    "synthesia": 0.40,
    "higgsfield": 0.56,
    "wan": 0.05,
    "mubert": 0.03,
    "stable_audio": 0.02,
    "fallback": 0.0,
}

PLATFORM_DEFAULT_TIERS: dict[str, str] = {
    "x": "bulk",
    "twitter": "bulk",
    "threads": "bulk",
    "reddit": "bulk",
    "snapchat": "bulk",
    "instagram": "standard",
    "tiktok": "standard",
    "youtube": "standard",
    "facebook": "standard",
    "linkedin": "standard",
    "pinterest": "standard",
    "telegram": "standard",
    "discord": "standard",
    "blog": "hero",
    "seo_authority": "hero",
    "email_newsletter": "hero",
    "medium": "hero",
    "substack": "hero",
}


def classify_task_tier(platform: str, is_promoted: bool = False, campaign_type: str = "organic") -> str:
    if is_promoted:
        return "hero"
    if campaign_type in ("paid", "sponsored", "hero"):
        return "hero"
    return PLATFORM_DEFAULT_TIERS.get(platform.lower(), "standard")


def route_to_provider(content_type: str, quality_tier: str) -> str:
    key = (content_type.lower(), quality_tier.lower())
    if key in ROUTING_TABLE:
        return ROUTING_TABLE[key]
    return TYPE_DEFAULTS.get(content_type.lower(), "gemini_flash")


def estimate_cost(provider_key: str, units: float = 1.0) -> float:
    return round(COST_PER_UNIT.get(provider_key, 0.01) * units, 4)


def check_budget_remaining(daily_budget: float, spent_today: float) -> dict[str, Any]:
    remaining = daily_budget - spent_today
    return {
        "within_budget": remaining > 0,
        "remaining_usd": round(remaining, 4),
        "spent_usd": round(spent_today, 4),
        "budget_usd": daily_budget,
        "utilization_pct": round((spent_today / max(daily_budget, 0.01)) * 100, 1),
    }


def compute_monthly_projection(posts_per_month: int = 300, platform_mix: dict[str, float] | None = None) -> dict[str, Any]:
    mix = platform_mix or {"instagram": 0.2, "tiktok": 0.2, "youtube": 0.1, "x": 0.4, "blog": 0.1}
    by_provider: dict[str, float] = {}
    total = 0.0

    for platform, share in mix.items():
        count = int(posts_per_month * share)
        tier = PLATFORM_DEFAULT_TIERS.get(platform, "standard")

        for ct in ["text", "image"]:
            prov = route_to_provider(ct, tier)
            cost = estimate_cost(prov)
            by_provider[prov] = by_provider.get(prov, 0) + cost * count
            total += cost * count

        if platform in ("tiktok", "youtube", "instagram", "facebook", "snapchat"):
            video_share = 0.5
            video_count = int(count * video_share)
            vprov = route_to_provider("video", tier)
            vcost = estimate_cost(vprov)
            by_provider[vprov] = by_provider.get(vprov, 0) + vcost * video_count
            total += vcost * video_count

    by_provider = {k: round(v, 2) for k, v in sorted(by_provider.items(), key=lambda x: -x[1])}
    return {
        "posts_per_month": posts_per_month,
        "total_estimated_usd": round(total, 2),
        "daily_average_usd": round(total / 30, 2),
        "cost_per_post_usd": round(total / max(posts_per_month, 1), 2),
        "by_provider": by_provider,
        "platform_mix": mix,
    }


def route_content_task(
    task_description: str,
    platform: str,
    content_type: str = "text",
    is_promoted: bool = False,
    campaign_type: str = "organic",
) -> dict[str, Any]:
    tier = classify_task_tier(platform, is_promoted, campaign_type)
    provider = route_to_provider(content_type, tier)
    cost = estimate_cost(provider)
    return {
        "content_type": content_type,
        "quality_tier": tier,
        "routed_provider": provider,
        "estimated_cost": cost,
        "platform": platform,
        "is_promoted": is_promoted,
        "explanation": f"{content_type} @ {tier} tier -> {provider} (est. ${cost:.4f})",
    }
