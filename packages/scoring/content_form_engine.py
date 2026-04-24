"""Content Form Selection + Mix Allocation Engine.

Selects the best content-form mix per account/platform/funnel stage.
Avatar is one option — not the default.
"""
from __future__ import annotations

from typing import Any

CONTENT_FORMS = [
    "avatar_led_video",
    "faceless_short_form",
    "voiceover_video",
    "text_led_post",
    "carousel_image",
    "long_form_video",
    "proof_testimonial",
    "product_demo",
    "founder_expert",
    "ugc_style",
    "hybrid_format",
]

FORMAT_FAMILIES = {
    "avatar_led_video": "video", "faceless_short_form": "video",
    "voiceover_video": "video", "long_form_video": "video",
    "product_demo": "video", "founder_expert": "video",
    "ugc_style": "video", "hybrid_format": "video",
    "text_led_post": "text", "carousel_image": "image",
    "proof_testimonial": "mixed",
}

SHORT_LONG = {
    "avatar_led_video": "short", "faceless_short_form": "short",
    "voiceover_video": "short", "text_led_post": "short",
    "carousel_image": "short", "ugc_style": "short",
    "hybrid_format": "short",
    "long_form_video": "long", "proof_testimonial": "long",
    "product_demo": "long", "founder_expert": "long",
}

AVATAR_MODES = {
    "avatar_led_video": "full_avatar",
    "voiceover_video": "voice_only",
    "hybrid_format": "avatar_overlay",
    "faceless_short_form": "none", "text_led_post": "none",
    "carousel_image": "none", "long_form_video": "none",
    "proof_testimonial": "none", "product_demo": "none",
    "founder_expert": "none", "ugc_style": "none",
}

COST_BANDS = {
    "text_led_post": "low", "carousel_image": "low",
    "faceless_short_form": "low", "ugc_style": "low",
    "voiceover_video": "medium", "proof_testimonial": "medium",
    "hybrid_format": "medium",
    "avatar_led_video": "high", "product_demo": "medium",
    "long_form_video": "high", "founder_expert": "high",
}

COST_ESTIMATES = {"low": 25.0, "medium": 75.0, "high": 200.0}

PLATFORM_FIT: dict[str, list[str]] = {
    "youtube": ["long_form_video", "voiceover_video", "avatar_led_video", "product_demo", "founder_expert"],
    "tiktok": ["faceless_short_form", "ugc_style", "avatar_led_video", "hybrid_format", "voiceover_video"],
    "instagram": ["carousel_image", "faceless_short_form", "ugc_style", "proof_testimonial", "avatar_led_video"],
    "twitter": ["text_led_post", "carousel_image", "faceless_short_form", "proof_testimonial"],
    "x": ["text_led_post", "carousel_image", "faceless_short_form", "proof_testimonial"],
    "linkedin": ["text_led_post", "carousel_image", "founder_expert", "proof_testimonial", "long_form_video"],
    "facebook": ["faceless_short_form", "ugc_style", "carousel_image", "avatar_led_video", "proof_testimonial"],
    "reddit": ["text_led_post", "proof_testimonial", "carousel_image"],
    "pinterest": ["carousel_image", "product_demo", "ugc_style"],
    "threads": ["text_led_post", "carousel_image"],
    "snapchat": ["faceless_short_form", "ugc_style", "hybrid_format"],
    "email_newsletter": ["text_led_post", "carousel_image", "proof_testimonial", "founder_expert", "long_form_video"],
    "blog": ["long_form_video", "proof_testimonial", "product_demo", "founder_expert", "carousel_image", "text_led_post"],
    "seo_authority": ["long_form_video", "proof_testimonial", "product_demo", "founder_expert", "text_led_post"],
    "telegram": ["text_led_post", "carousel_image", "voiceover_video"],
    "discord": ["text_led_post", "faceless_short_form", "ugc_style"],
    "medium": ["text_led_post", "proof_testimonial", "founder_expert", "long_form_video"],
    "substack": ["text_led_post", "proof_testimonial", "founder_expert", "long_form_video", "voiceover_video"],
}

FUNNEL_STAGE_FIT: dict[str, list[str]] = {
    "awareness": ["faceless_short_form", "ugc_style", "avatar_led_video", "text_led_post", "carousel_image"],
    "consideration": ["voiceover_video", "proof_testimonial", "product_demo", "long_form_video", "founder_expert"],
    "conversion": ["proof_testimonial", "product_demo", "avatar_led_video", "founder_expert", "ugc_style"],
    "retention": ["long_form_video", "founder_expert", "text_led_post", "hybrid_format"],
}

MONETIZATION_FIT: dict[str, list[str]] = {
    "affiliate": ["faceless_short_form", "ugc_style", "voiceover_video", "text_led_post"],
    "sponsorship": ["long_form_video", "avatar_led_video", "voiceover_video", "founder_expert"],
    "digital_product": ["proof_testimonial", "founder_expert", "long_form_video", "product_demo"],
    "membership": ["founder_expert", "long_form_video", "proof_testimonial"],
    "coaching": ["avatar_led_video", "founder_expert", "proof_testimonial"],
    "ads": ["faceless_short_form", "text_led_post", "carousel_image"],
}


def _score_form(
    form: str,
    platform: str,
    monetization: str,
    funnel_stage: str,
    saturation: float,
    fatigue: float,
    has_avatar: bool,
    has_voice: bool,
    account_maturity: str,
    trust_need: str,
) -> float:
    """0-1 composite score for a content form given context."""
    s = 0.0

    if form in PLATFORM_FIT.get(platform, []):
        rank = PLATFORM_FIT[platform].index(form)
        s += 0.25 * (1.0 - rank / max(1, len(PLATFORM_FIT[platform])))

    if form in MONETIZATION_FIT.get(monetization, []):
        s += 0.20

    if form in FUNNEL_STAGE_FIT.get(funnel_stage, []):
        s += 0.15

    avatar_mode = AVATAR_MODES.get(form, "none")
    if avatar_mode != "none" and not has_avatar:
        s -= 0.30
    if avatar_mode == "voice_only" and not has_voice:
        s -= 0.15

    if fatigue > 0.6 and form in ("avatar_led_video", "long_form_video"):
        s -= 0.10
    if saturation > 0.7 and form in ("faceless_short_form", "text_led_post"):
        s += 0.10

    if trust_need == "high" and form in ("proof_testimonial", "founder_expert", "product_demo"):
        s += 0.15
    if trust_need == "low" and COST_BANDS.get(form) == "low":
        s += 0.05

    if account_maturity == "new" and COST_BANDS.get(form) == "low":
        s += 0.10
    if account_maturity == "mature" and form in ("long_form_video", "founder_expert"):
        s += 0.10

    return round(max(0, min(1, s)), 3)


def recommend_content_forms(
    platform: str,
    monetization: str = "affiliate",
    funnel_stage: str = "awareness",
    saturation: float = 0.0,
    fatigue: float = 0.0,
    has_avatar: bool = False,
    has_voice: bool = False,
    account_maturity: str = "new",
    trust_need: str = "low",
    niche: str = "general",
    account_id: str | None = None,
) -> list[dict[str, Any]]:
    """Score all content forms and return ranked list."""
    scored: list[tuple[float, str]] = []
    for form in CONTENT_FORMS:
        sc = _score_form(form, platform, monetization, funnel_stage, saturation, fatigue, has_avatar, has_voice, account_maturity, trust_need)
        scored.append((sc, form))

    scored.sort(reverse=True)
    results: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []

    for rank, (sc, form) in enumerate(scored[:5]):
        avatar_mode = AVATAR_MODES.get(form, "none")
        if avatar_mode == "full_avatar" and not has_avatar:
            blockers.append({"content_form": form, "blocker_type": "no_avatar_provider", "severity": "high", "description": "Avatar provider not configured. Cannot produce avatar-led video.", "operator_action": "Configure Tavus or HeyGen avatar provider."})
        if avatar_mode == "voice_only" and not has_voice:
            blockers.append({"content_form": form, "blocker_type": "no_voice_provider", "severity": "medium", "description": "Voice provider not configured. Voiceover will use TTS fallback.", "operator_action": "Configure ElevenLabs voice provider."})

        cost_band = COST_BANDS.get(form, "medium")
        upside = round(sc * 500 + 50, 2)
        cost = COST_ESTIMATES.get(cost_band, 75.0)

        results.append({
            "platform": platform,
            "account_id": account_id,
            "recommended_content_form": form,
            "secondary_content_form": scored[rank + 1][1] if rank + 1 < len(scored) else None,
            "format_family": FORMAT_FAMILIES.get(form, "mixed"),
            "short_or_long": SHORT_LONG.get(form, "short"),
            "avatar_mode": avatar_mode,
            "trust_level_required": trust_need,
            "production_cost_band": cost_band,
            "expected_upside": upside,
            "expected_cost": cost,
            "confidence": round(min(0.95, 0.4 + sc), 3),
            "urgency": round(min(100, 30 + saturation * 40 + fatigue * 30), 1),
            "explanation": (
                f"{form.replace('_', ' ').title()} for {platform} ({funnel_stage} stage, {monetization} path). "
                f"Score {sc:.2f}. Avatar: {avatar_mode}. Cost: {cost_band}."
            ),
            "truth_label": "recommendation",
            "blockers": [b for b in blockers if b["content_form"] == form],
        })

    return results


def compute_mix_reports(
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate recommendations into mix allocation reports by dimension."""
    reports: list[dict[str, Any]] = []

    by_platform: dict[str, list[dict]] = {}
    for r in recommendations:
        by_platform.setdefault(r["platform"], []).append(r)

    for plat, recs in by_platform.items():
        mix: dict[str, float] = {}
        total_up = sum(r["expected_upside"] for r in recs)
        for r in recs:
            form = r["recommended_content_form"]
            mix[form] = mix.get(form, 0) + (r["expected_upside"] / max(1, total_up))
        mix = {k: round(v, 3) for k, v in sorted(mix.items(), key=lambda x: -x[1])}
        avg_conf = sum(r["confidence"] for r in recs) / max(1, len(recs))
        reports.append({
            "dimension": "platform",
            "dimension_value": plat,
            "mix_allocation": mix,
            "total_expected_upside": round(total_up, 2),
            "avg_confidence": round(avg_conf, 3),
            "explanation": f"Content form mix for {plat}: {len(recs)} forms scored.",
        })

    for stage in ("awareness", "consideration", "conversion", "retention"):
        [r for r in recommendations if r.get("details_json", {}).get("funnel_stage") == stage or True]
        forms_for_stage = FUNNEL_STAGE_FIT.get(stage, [])
        if forms_for_stage:
            n = len(forms_for_stage)
            mix = {f: round(1.0 / n, 3) for f in forms_for_stage[:5]}
            reports.append({
                "dimension": "funnel_stage",
                "dimension_value": stage,
                "mix_allocation": mix,
                "total_expected_upside": 0.0,
                "avg_confidence": 0.6,
                "explanation": f"Recommended forms for {stage} stage.",
            })

    return reports


def detect_content_form_blockers(
    has_avatar: bool,
    has_voice: bool,
    content_count: int,
    offer_count: int,
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if not has_avatar:
        blockers.append({"content_form": "avatar_led_video", "blocker_type": "no_avatar_provider", "severity": "high", "description": "No avatar provider configured. Avatar-led content is blocked.", "operator_action": "Set TAVUS_API_KEY or HEYGEN_API_KEY."})
    if not has_voice:
        blockers.append({"content_form": "voiceover_video", "blocker_type": "no_voice_provider", "severity": "medium", "description": "No voice provider configured. Voiceover content uses fallback TTS.", "operator_action": "Set ELEVENLABS_API_KEY."})
    if content_count == 0:
        blockers.append({"content_form": "all", "blocker_type": "no_content_history", "severity": "high", "description": "No content items. Cannot optimize mix without prior performance data.", "operator_action": "Create at least 5 content items."})
    if offer_count == 0:
        blockers.append({"content_form": "all", "blocker_type": "no_offers", "severity": "high", "description": "No offers defined. Monetization-path optimization requires offers.", "operator_action": "Create at least one offer."})
    return blockers
