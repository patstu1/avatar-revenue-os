"""Campaign Constructor Engine — build, variant, detect blockers. Pure functions."""

from __future__ import annotations

from typing import Any

CAMPAIGN_TYPES = [
    "affiliate",
    "lead_gen",
    "product_conversion",
    "creator_revenue",
    "sponsor",
    "newsletter_growth",
    "authority_building",
    "experiment",
]


def construct_campaign(
    offer: dict[str, Any],
    brand: dict[str, Any],
    accounts: list[dict[str, Any]],
    landing_page_id: str | None = None,
    campaign_type: str = "affiliate",
) -> dict[str, Any]:
    name = offer.get("name", "Campaign")
    method = offer.get("monetization_method", "affiliate")
    platforms = list({a.get("platform", "") for a in accounts if a.get("platform")})
    acct_ids = [str(a.get("id", "")) for a in accounts]
    niche = brand.get("niche", "general")

    objective = _objective_for_type(campaign_type, name, method)
    hook = _default_hook(campaign_type)
    cta = _default_cta(campaign_type)
    followup = _default_followup(campaign_type)
    upside = _estimate_upside(offer, len(accounts))
    cost = _estimate_cost(campaign_type, len(accounts))

    return {
        "campaign_type": campaign_type,
        "campaign_name": f"{campaign_type.replace('_', ' ').title()}: {name}",
        "objective": objective,
        "target_platforms": platforms,
        "target_accounts": acct_ids,
        "target_audience": f"{niche} audience interested in {name}",
        "content_family": "short_video" if any(p in ("tiktok", "instagram") for p in platforms) else "long_video",
        "hook_family": hook,
        "cta_family": cta,
        "monetization_path": method,
        "followup_path": followup,
        "budget_tier": "hero" if upside > 30 else "bulk",
        "expected_upside": round(upside, 2),
        "expected_cost": round(cost, 2),
        "confidence": round(min(1.0, 0.3 + len(accounts) * 0.1 + (0.2 if landing_page_id else 0)), 3),
        "landing_page_id": landing_page_id,
        "launch_status": "draft",
        "truth_label": "recommendation_only",
    }


def construct_variant(campaign: dict[str, Any], idx: int = 1) -> dict[str, Any]:
    hooks = ["curiosity", "direct_pain", "comparison", "authority_led", "testimonial_led"]
    ctas = ["direct", "soft", "urgency", "comment_to_get", "save_share"]
    return {
        "variant_label": f"variant_{idx}",
        "hook_family": hooks[idx % len(hooks)],
        "cta_family": ctas[idx % len(ctas)],
        "is_control": idx == 0,
    }


def detect_blockers(campaign: dict[str, Any], system_state: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    if not campaign.get("target_accounts"):
        blockers.append(
            {"blocker_type": "no_accounts", "description": "Campaign has no target accounts", "severity": "critical"}
        )
    if not campaign.get("landing_page_id") and campaign.get("campaign_type") not in (
        "authority_building",
        "newsletter_growth",
    ):
        blockers.append(
            {
                "blocker_type": "no_landing_page",
                "description": "No landing page linked — monetization has no destination",
                "severity": "high",
            }
        )
    if not campaign.get("monetization_path"):
        blockers.append(
            {"blocker_type": "no_monetization", "description": "No monetization path defined", "severity": "high"}
        )

    suppressed_hooks = system_state.get("suppressed_families", [])
    if campaign.get("hook_family") in suppressed_hooks:
        blockers.append(
            {
                "blocker_type": "suppressed_hook",
                "description": f"Hook family '{campaign['hook_family']}' is suppressed",
                "severity": "high",
            }
        )

    provider_blockers = system_state.get("provider_blockers", [])
    if provider_blockers:
        blockers.append(
            {
                "blocker_type": "provider_blocked",
                "description": f"{len(provider_blockers)} provider(s) blocked",
                "severity": "medium",
            }
        )

    return blockers


def _objective_for_type(ct: str, name: str, method: str) -> str:
    m = {
        "affiliate": f"Drive affiliate conversions for {name} via {method}",
        "lead_gen": f"Capture leads for {name}",
        "product_conversion": f"Convert audience to {name} buyers",
        "creator_revenue": f"Generate creator revenue from {name}",
        "sponsor": f"Execute sponsor campaign for {name}",
        "newsletter_growth": "Grow newsletter subscribers",
        "authority_building": f"Build authority in {name} space",
        "experiment": f"Test hypothesis about {name}",
    }
    return m.get(ct, f"Execute campaign for {name}")


def _default_hook(ct: str) -> str:
    return {
        "affiliate": "curiosity",
        "lead_gen": "free_value",
        "product_conversion": "direct_pain",
        "creator_revenue": "authority_led",
        "sponsor": "brand_fit",
        "newsletter_growth": "curiosity",
        "authority_building": "authority_led",
        "experiment": "curiosity",
    }.get(ct, "curiosity")


def _default_cta(ct: str) -> str:
    return {
        "affiliate": "product_click",
        "lead_gen": "newsletter_signup",
        "product_conversion": "direct",
        "creator_revenue": "direct",
        "sponsor": "soft",
        "newsletter_growth": "newsletter_signup",
        "authority_building": "save_share",
        "experiment": "soft",
    }.get(ct, "direct")


def _default_followup(ct: str) -> str:
    return {
        "affiliate": "email_sequence",
        "lead_gen": "nurture_sequence",
        "product_conversion": "cart_abandon_sequence",
        "creator_revenue": "onboarding_sequence",
        "sponsor": "report_delivery",
        "newsletter_growth": "welcome_sequence",
        "authority_building": "content_drip",
        "experiment": "observation_only",
    }.get(ct, "email_followup")


def _estimate_upside(offer: dict, acct_count: int) -> float:
    epc = float(offer.get("epc", 1) or 1)
    cvr = float(offer.get("conversion_rate", 0.03) or 0.03)
    return epc * cvr * 1000 * max(1, acct_count)


def _estimate_cost(ct: str, acct_count: int) -> float:
    base = {
        "affiliate": 5,
        "lead_gen": 10,
        "product_conversion": 15,
        "creator_revenue": 20,
        "sponsor": 5,
        "newsletter_growth": 3,
        "authority_building": 8,
        "experiment": 5,
    }.get(ct, 5)
    return base * max(1, acct_count)
