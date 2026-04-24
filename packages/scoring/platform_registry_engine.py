"""Platform Registry Engine — source of truth for all content destination platforms.

Every platform must have an explicit publish_mode and execution_truth label.
No vague "supported" without stating how content gets there.
"""
from __future__ import annotations

import os
from typing import Any

PUBLISH_MODES = {
    "buffer": "Automated via Buffer API",
    "direct_api": "Automated via platform-specific API client",
    "esp_service": "Automated via ESP/email service (live execution layer)",
    "manual": "Manual publish by operator — no automated path",
    "recommendation_only": "System recommends content but operator must publish manually",
}

PLATFORM_REGISTRY: list[dict[str, Any]] = [
    # ── P0: Core Platforms (Buffer-automated) ────────────────────────
    {
        "platform_key": "instagram", "display_name": "Instagram", "priority": 0,
        "content_role": "visual_engagement",
        "supported_forms": ["carousel_image", "faceless_short_form", "ugc_style", "proof_testimonial", "avatar_led_video", "hybrid_format"],
        "monetization_suitability": {"affiliate": 0.8, "sponsorship": 0.9, "digital_product": 0.6, "ads": 0.5},
        "constraints": {"max_caption": 2200, "max_hashtags": 30, "video_max_sec": 90, "image_sizes": {"feed": [1080, 1080], "story": [1080, 1920], "reel": [1080, 1920]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "instagram_insights", "expansion_suitability": 0.85,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    {
        "platform_key": "tiktok", "display_name": "TikTok", "priority": 0,
        "content_role": "viral_short_form",
        "supported_forms": ["faceless_short_form", "ugc_style", "avatar_led_video", "hybrid_format", "voiceover_video"],
        "monetization_suitability": {"affiliate": 0.9, "sponsorship": 0.7, "digital_product": 0.5, "ads": 0.6},
        "constraints": {"max_caption": 2200, "max_hashtags": 5, "video_max_sec": 180, "image_sizes": {"video": [1080, 1920]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "tiktok_analytics", "expansion_suitability": 0.90,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    {
        "platform_key": "youtube", "display_name": "YouTube", "priority": 0,
        "content_role": "authority_video",
        "supported_forms": ["long_form_video", "voiceover_video", "avatar_led_video", "product_demo", "founder_expert"],
        "monetization_suitability": {"affiliate": 0.85, "sponsorship": 0.95, "digital_product": 0.8, "membership": 0.7, "ads": 0.9},
        "constraints": {"max_caption": 5000, "max_hashtags": 15, "video_max_sec": 60, "image_sizes": {"thumbnail": [1280, 720], "short": [1080, 1920]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "youtube_analytics", "expansion_suitability": 0.80,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    {
        "platform_key": "twitter", "display_name": "X / Twitter", "priority": 0,
        "content_role": "engagement_text",
        "supported_forms": ["text_led_post", "carousel_image", "faceless_short_form", "proof_testimonial"],
        "monetization_suitability": {"affiliate": 0.7, "sponsorship": 0.4, "digital_product": 0.5},
        "constraints": {"max_caption": 280, "max_hashtags": 3, "video_max_sec": 140, "image_sizes": {"post": [1200, 675]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "x_analytics", "expansion_suitability": 0.70,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    {
        "platform_key": "blog", "display_name": "Blog / Website", "priority": 0,
        "content_role": "seo_authority",
        "supported_forms": ["text_led_post", "long_form_video", "proof_testimonial", "product_demo", "founder_expert", "carousel_image"],
        "monetization_suitability": {"affiliate": 0.95, "sponsorship": 0.6, "digital_product": 0.9, "ads": 0.8},
        "constraints": {"max_caption": None, "max_hashtags": 10, "video_max_sec": None, "image_sizes": {"hero": [1200, 630], "inline": [800, 450]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "google_analytics", "expansion_suitability": 0.75,
        "credential_env": None, "blocker_state": "no_cms_client",
    },
    # ── P1: Expansion Platforms ──────────────────────────────────────
    {
        "platform_key": "facebook", "display_name": "Facebook", "priority": 1,
        "content_role": "community_engagement",
        "supported_forms": ["faceless_short_form", "ugc_style", "carousel_image", "avatar_led_video", "proof_testimonial", "text_led_post"],
        "monetization_suitability": {"affiliate": 0.7, "sponsorship": 0.6, "digital_product": 0.5, "ads": 0.8},
        "constraints": {"max_caption": 63206, "max_hashtags": 10, "video_max_sec": 240, "image_sizes": {"post": [1200, 630], "story": [1080, 1920]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "meta_insights", "expansion_suitability": 0.65,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    {
        "platform_key": "pinterest", "display_name": "Pinterest", "priority": 1,
        "content_role": "visual_discovery",
        "supported_forms": ["carousel_image", "product_demo", "ugc_style"],
        "monetization_suitability": {"affiliate": 0.9, "digital_product": 0.7, "ads": 0.5},
        "constraints": {"max_caption": 500, "max_hashtags": 20, "video_max_sec": 60, "image_sizes": {"pin": [1000, 1500]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "pinterest_analytics", "expansion_suitability": 0.70,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    {
        "platform_key": "reddit", "display_name": "Reddit", "priority": 1,
        "content_role": "community_authority",
        "supported_forms": ["text_led_post", "proof_testimonial", "carousel_image"],
        "monetization_suitability": {"affiliate": 0.5, "digital_product": 0.4},
        "constraints": {"max_caption": 40000, "max_hashtags": 0, "video_max_sec": 900, "image_sizes": {"post": [1200, 628]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "reddit_api", "expansion_suitability": 0.55,
        "credential_env": None, "blocker_state": "no_direct_publish_client",
    },
    {
        "platform_key": "linkedin", "display_name": "LinkedIn", "priority": 1,
        "content_role": "b2b_authority",
        "supported_forms": ["text_led_post", "carousel_image", "founder_expert", "proof_testimonial", "long_form_video"],
        "monetization_suitability": {"consulting": 0.9, "sponsorship": 0.7, "digital_product": 0.6, "lead_gen": 0.85},
        "constraints": {"max_caption": 3000, "max_hashtags": 5, "video_max_sec": 600, "image_sizes": {"post": [1200, 627]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "linkedin_analytics", "expansion_suitability": 0.75,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    # ── P2: Extended Platforms ───────────────────────────────────────
    {
        "platform_key": "threads", "display_name": "Threads", "priority": 2,
        "content_role": "micro_engagement",
        "supported_forms": ["text_led_post", "carousel_image"],
        "monetization_suitability": {"affiliate": 0.4, "digital_product": 0.3},
        "constraints": {"max_caption": 500, "max_hashtags": 0, "video_max_sec": 300, "image_sizes": {"post": [1080, 1080]}},
        "buffer_supported": True, "publish_mode": "buffer", "execution_truth": "live_when_configured",
        "analytics_source": "threads_insights", "expansion_suitability": 0.45,
        "credential_env": "BUFFER_API_KEY", "blocker_state": None,
    },
    {
        "platform_key": "snapchat", "display_name": "Snapchat", "priority": 2,
        "content_role": "ephemeral_engagement",
        "supported_forms": ["faceless_short_form", "ugc_style", "hybrid_format"],
        "monetization_suitability": {"sponsorship": 0.5, "ads": 0.4},
        "constraints": {"max_caption": 250, "max_hashtags": 0, "video_max_sec": 60, "image_sizes": {"snap": [1080, 1920]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "snapchat_insights", "expansion_suitability": 0.35,
        "credential_env": None, "blocker_state": "no_direct_publish_client",
    },
    {
        "platform_key": "email_newsletter", "display_name": "Email Newsletter", "priority": 2,
        "content_role": "owned_audience_conversion",
        "supported_forms": ["text_led_post", "carousel_image", "proof_testimonial", "founder_expert", "long_form_video"],
        "monetization_suitability": {"affiliate": 0.95, "digital_product": 0.95, "sponsorship": 0.8, "membership": 0.9},
        "constraints": {"max_caption": None, "max_hashtags": 0, "video_max_sec": None, "image_sizes": {"header": [600, 200], "inline": [600, 400]}},
        "buffer_supported": False, "publish_mode": "esp_service", "execution_truth": "live_when_configured",
        "analytics_source": "esp_analytics", "expansion_suitability": 0.90,
        "credential_env": "SMTP_HOST", "blocker_state": "blocked_without_esp",
    },
    {
        "platform_key": "seo_authority", "display_name": "SEO Authority Pages", "priority": 2,
        "content_role": "organic_search_capture",
        "supported_forms": ["text_led_post", "long_form_video", "proof_testimonial", "product_demo", "founder_expert"],
        "monetization_suitability": {"affiliate": 0.95, "digital_product": 0.9, "ads": 0.85, "lead_gen": 0.8},
        "constraints": {"max_caption": None, "max_hashtags": 0, "video_max_sec": None, "image_sizes": {"hero": [1200, 630]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "google_search_console", "expansion_suitability": 0.80,
        "credential_env": None, "blocker_state": "no_cms_client",
    },
    # ── P3: Optional / Community Platforms ───────────────────────────
    {
        "platform_key": "telegram", "display_name": "Telegram", "priority": 3,
        "content_role": "direct_community",
        "supported_forms": ["text_led_post", "carousel_image", "voiceover_video"],
        "monetization_suitability": {"affiliate": 0.7, "digital_product": 0.6, "membership": 0.8},
        "constraints": {"max_caption": 4096, "max_hashtags": 0, "video_max_sec": None, "image_sizes": {"post": [1280, 720]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "telegram_bot_api", "expansion_suitability": 0.50,
        "credential_env": None, "blocker_state": "no_direct_publish_client",
    },
    {
        "platform_key": "discord", "display_name": "Discord", "priority": 3,
        "content_role": "community_hub",
        "supported_forms": ["text_led_post", "faceless_short_form", "ugc_style"],
        "monetization_suitability": {"membership": 0.85, "digital_product": 0.5, "consulting": 0.4},
        "constraints": {"max_caption": 2000, "max_hashtags": 0, "video_max_sec": None, "image_sizes": {"embed": [1280, 720]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "discord_bot_api", "expansion_suitability": 0.45,
        "credential_env": None, "blocker_state": "no_direct_publish_client",
    },
    {
        "platform_key": "medium", "display_name": "Medium", "priority": 3,
        "content_role": "thought_leadership",
        "supported_forms": ["text_led_post", "proof_testimonial", "founder_expert", "long_form_video"],
        "monetization_suitability": {"affiliate": 0.6, "digital_product": 0.7, "consulting": 0.8},
        "constraints": {"max_caption": None, "max_hashtags": 5, "video_max_sec": None, "image_sizes": {"hero": [1400, 788]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "medium_stats", "expansion_suitability": 0.55,
        "credential_env": None, "blocker_state": "no_direct_publish_client",
    },
    {
        "platform_key": "substack", "display_name": "Substack", "priority": 3,
        "content_role": "paid_newsletter",
        "supported_forms": ["text_led_post", "proof_testimonial", "founder_expert", "long_form_video", "voiceover_video"],
        "monetization_suitability": {"membership": 0.95, "digital_product": 0.8, "affiliate": 0.7, "sponsorship": 0.6},
        "constraints": {"max_caption": None, "max_hashtags": 0, "video_max_sec": None, "image_sizes": {"hero": [1456, 816]}},
        "buffer_supported": False, "publish_mode": "manual", "execution_truth": "recommendation_only",
        "analytics_source": "substack_dashboard", "expansion_suitability": 0.70,
        "credential_env": None, "blocker_state": "no_direct_publish_client",
    },
]

BUFFER_SUPPORTED_PLATFORMS = [p["platform_key"] for p in PLATFORM_REGISTRY if p["buffer_supported"]]
PLATFORM_BY_KEY = {p["platform_key"]: p for p in PLATFORM_REGISTRY}


def get_platform_info(platform_key: str) -> dict[str, Any] | None:
    return PLATFORM_BY_KEY.get(platform_key.lower())


def get_platforms_by_priority(max_priority: int = 3) -> list[dict[str, Any]]:
    return [p for p in PLATFORM_REGISTRY if p["priority"] <= max_priority]


def get_monetization_fit(platform_key: str, method: str) -> float:
    p = PLATFORM_BY_KEY.get(platform_key.lower())
    if not p:
        return 0.0
    return p.get("monetization_suitability", {}).get(method, 0.0)


def get_expansion_candidates(min_suitability: float = 0.6) -> list[dict[str, Any]]:
    return sorted(
        [p for p in PLATFORM_REGISTRY if p["expansion_suitability"] >= min_suitability],
        key=lambda p: -p["expansion_suitability"],
    )


def get_platform_readiness(platform_key: str) -> dict[str, Any]:
    """Return execution readiness for a platform with honest truth labels."""
    p = PLATFORM_BY_KEY.get(platform_key.lower())
    if not p:
        return {"platform": platform_key, "ready": False, "execution_truth": "unknown_platform", "blocker": "Platform not in registry"}

    cred_env = p.get("credential_env")
    cred_present = bool(os.environ.get(cred_env, "")) if cred_env else True
    publish_mode = p["publish_mode"]

    if publish_mode == "buffer":
        ready = cred_present
        truth = "live" if ready else "blocked_by_credentials"
        blocker = None if ready else f"Set {cred_env} to enable Buffer publishing"
    elif publish_mode == "esp_service":
        ready = cred_present
        truth = "live" if ready else "blocked_by_credentials"
        blocker = None if ready else f"Set {cred_env} to enable email delivery"
    elif publish_mode == "manual":
        ready = False
        truth = "recommendation_only"
        blocker = p.get("blocker_state") or "manual_publish_required"
    elif publish_mode == "recommendation_only":
        ready = False
        truth = "recommendation_only"
        blocker = "no_automated_publish_path"
    else:
        ready = False
        truth = "unknown"
        blocker = "publish_mode_not_recognized"

    return {
        "platform": platform_key,
        "display_name": p["display_name"],
        "publish_mode": publish_mode,
        "buffer_supported": p["buffer_supported"],
        "credential_env": cred_env,
        "credential_present": cred_present,
        "ready": ready,
        "execution_truth": truth,
        "blocker": blocker,
    }


def detect_platform_blockers(platform_key: str) -> list[dict[str, str]]:
    r = get_platform_readiness(platform_key)
    blockers = []
    if r["blocker"]:
        blockers.append({"type": r["blocker"], "description": f"{r['display_name']}: {r['blocker']} (publish_mode={r['publish_mode']}, truth={r['execution_truth']})"})
    return blockers


def get_all_platform_readiness() -> list[dict[str, Any]]:
    return [get_platform_readiness(p["platform_key"]) for p in PLATFORM_REGISTRY]
