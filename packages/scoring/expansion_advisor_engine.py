"""Account Expansion Advisor Engine — execution-grade expand/hold decisions.

Consumes scale engine outputs + account health signals and produces
a single, opinionated advisory: add now, or hold (with exact reasons).
"""
from __future__ import annotations

from typing import Any

CONTENT_ROLES = {
    "add_experimental": "experimental", "add_experimental_account": "experimental",
    "add_platform_specific": "flagship_secondary", "add_platform_specific_account": "flagship_secondary",
    "add_niche_spinoff": "niche_specialist", "add_niche_spinoff_account": "niche_specialist",
    "add_localized": "geo_language_specialist", "add_localized_language_account": "geo_language_specialist",
    "add_trend_capture": "trend_hunter", "add_trend_capture_account": "trend_hunter",
    "add_evergreen_authority": "authority_evergreen", "add_evergreen_authority_account": "authority_evergreen",
    "add_offer_first": None, "add_new_offer_before_adding_account": None,
    "scale_winners_harder": None, "scale_current_winners_harder": None,
    "improve_funnel": None, "improve_funnel_before_scaling": None,
    "do_not_scale_yet": None,
    "monitor": None,
}

ACCOUNT_TYPES = {
    "add_experimental": "experimental", "add_experimental_account": "experimental",
    "add_platform_specific": "organic", "add_platform_specific_account": "organic",
    "add_niche_spinoff": "organic", "add_niche_spinoff_account": "organic",
    "add_localized": "organic", "add_localized_language_account": "organic",
    "add_trend_capture": "hybrid", "add_trend_capture_account": "hybrid",
    "add_evergreen_authority": "organic", "add_evergreen_authority_account": "organic",
    "add_offer_specific": "organic", "add_offer_specific_account": "organic",
}

MONETIZATION_PATHS = {
    "add_experimental": "Mirror flagship monetization — same offers, experimental creative angles",
    "add_experimental_account": "Mirror flagship monetization — same offers, experimental creative angles",
    "add_platform_specific": "Platform-native monetization — adapt offers to new platform's conversion patterns",
    "add_platform_specific_account": "Platform-native monetization — adapt offers to new platform's conversion patterns",
    "add_niche_spinoff": "Sub-niche monetization — targeted offers for the separated audience segment",
    "add_niche_spinoff_account": "Sub-niche monetization — targeted offers for the separated audience segment",
    "add_localized": "Localized monetization — region-specific offers and language-adapted funnels",
    "add_localized_language_account": "Localized monetization — region-specific offers and language-adapted funnels",
    "add_trend_capture": "Quick-conversion monetization — affiliate/CPA offers with short attribution windows",
    "add_trend_capture_account": "Quick-conversion monetization — affiliate/CPA offers with short attribution windows",
    "add_evergreen_authority": "Authority monetization — premium offers, courses, consulting funnels",
    "add_evergreen_authority_account": "Authority monetization — premium offers, courses, consulting funnels",
    "add_offer_specific": "Offer-aligned monetization — dedicated CTA for split conversion intent",
    "add_offer_specific_account": "Offer-aligned monetization — dedicated CTA for split conversion intent",
}

EXPAND_REC_KEYS = {
    "add_experimental", "add_experimental_account",
    "add_platform_specific", "add_platform_specific_account",
    "add_niche_spinoff", "add_niche_spinoff_account",
    "add_localized", "add_localized_language_account",
    "add_trend_capture", "add_trend_capture_account",
    "add_evergreen_authority", "add_evergreen_authority_account",
    "add_offer_specific", "add_offer_specific_account",
}

HOLD_REC_KEYS = {
    "scale_winners_harder", "scale_current_winners_harder",
    "improve_funnel", "improve_funnel_before_scaling",
    "do_not_scale_yet",
    "monitor",
    "add_offer_first", "add_new_offer_before_adding_account",
    "reduce_weak", "reduce_or_suppress_weak_account",
}

TIME_TO_SIGNAL = {
    "add_experimental": 21, "add_experimental_account": 21,
    "add_platform_specific": 30, "add_platform_specific_account": 30,
    "add_niche_spinoff": 28, "add_niche_spinoff_account": 28,
    "add_localized": 35, "add_localized_language_account": 35,
    "add_trend_capture": 14, "add_trend_capture_account": 14,
    "add_evergreen_authority": 45, "add_evergreen_authority_account": 45,
    "add_offer_specific": 25, "add_offer_specific_account": 25,
}


def compute_expansion_advisory(
    scale_result: dict[str, Any],
    accounts: list[dict[str, Any]],
    brand_niche: str | None,
    brand_sub_niche: str | None,
    offer_count: int,
    content_count: int,
    avg_account_health: str = "healthy",
    avg_fatigue: float = 0.0,
    avg_saturation: float = 0.0,
) -> dict[str, Any]:
    """Produce a single expansion advisory from scale engine output + signals.

    Returns the exact fields required by AccountExpansionAdvisory.
    """
    rec_key = scale_result.get("recommendation_key", "monitor")
    best_next = scale_result.get("best_next_account", {})
    inc_new = float(scale_result.get("incremental_profit_new_account", 0))
    inc_exist = float(scale_result.get("incremental_profit_more_volume", inc_new))
    readiness = float(scale_result.get("scale_readiness_score", 0))
    exp_conf = float(scale_result.get("expansion_confidence", 0))
    cann = float(scale_result.get("cannibalization_risk", 0))
    seg_sep = float(scale_result.get("audience_segment_separation", 0))
    explanation_raw = scale_result.get("explanation", "")

    should_add = rec_key in EXPAND_REC_KEYS
    hold_reason: str | None = None
    blockers: list[dict[str, str]] = []

    if not should_add:
        if rec_key in ("do_not_scale_yet",):
            hold_reason = f"Scale readiness {readiness:.0f}/100 below safe threshold. Fix fundamentals first."
        elif rec_key in ("improve_funnel", "improve_funnel_before_scaling"):
            hold_reason = "Funnel bottleneck detected. Fix CTR/conversion before adding surface area."
        elif rec_key in ("add_offer_first", "add_new_offer_before_adding_account"):
            hold_reason = "Offer catalog too thin. Diversify monetization before expanding accounts."
        elif rec_key in ("scale_winners_harder", "scale_current_winners_harder"):
            hold_reason = f"Pushing existing accounts harder yields ${inc_exist:.0f}/wk vs ${inc_new:.0f}/wk for a new account. Scale winners first."
        else:
            hold_reason = f"Expansion not justified yet. Incremental new=${inc_new:.0f}, existing=${inc_exist:.0f}, readiness={readiness:.0f}."

    if offer_count == 0:
        blockers.append({"type": "no_offers", "description": "No offers defined. Cannot monetize a new account."})
        should_add = False
        hold_reason = (hold_reason or "") + " No offers in catalog."
    if content_count < 5:
        blockers.append({"type": "low_content", "description": "Fewer than 5 content items. Prove content capability first."})
    if avg_account_health == "critical":
        blockers.append({"type": "unhealthy_accounts", "description": "Existing accounts in critical health. Stabilize before expanding."})
        should_add = False
        hold_reason = (hold_reason or "") + " Existing accounts unhealthy."
    if avg_fatigue > 0.7:
        blockers.append({"type": "high_fatigue", "description": f"Average fatigue {avg_fatigue:.0%}. Audience fatigue risk too high for expansion."})
    if avg_saturation > 0.8:
        if should_add:
            pass  # saturation supports expansion
        blockers_note = {"type": "high_saturation", "description": f"Saturation {avg_saturation:.0%} — current accounts near ceiling. Supports expansion case."}
        if not should_add:
            blockers.append(blockers_note)

    platform = best_next.get("platform_suggestion", "tiktok") if should_add else None
    content_role = CONTENT_ROLES.get(rec_key) if should_add else None
    account_type = ACCOUNT_TYPES.get(rec_key, "organic") if should_add else None
    monetization_path = MONETIZATION_PATHS.get(rec_key) if should_add else None
    time_to_signal = TIME_TO_SIGNAL.get(rec_key, 21) if should_add else 0

    cost_estimate = 150.0 if account_type == "organic" else 300.0
    upside_weekly = inc_new if should_add else 0.0
    upside_monthly = upside_weekly * 4.3

    confidence = round(min(0.95, exp_conf * 0.6 + (readiness / 100) * 0.3 + (1.0 - cann) * 0.1), 3)
    urgency = round(min(100, readiness * 0.4 + avg_saturation * 60 + (30 if should_add else 0)), 1)

    if should_add:
        explanation = (
            f"EXPAND NOW: {explanation_raw} "
            f"New account incremental profit ${inc_new:.0f}/wk vs existing push ${inc_exist:.0f}/wk. "
            f"Readiness {readiness:.0f}/100, confidence {confidence:.0%}, cannibalization {cann:.0%}."
        )
    else:
        explanation = (
            f"HOLD: {hold_reason} "
            f"New=${inc_new:.0f}/wk, existing=${inc_exist:.0f}/wk. "
            f"Readiness {readiness:.0f}/100, confidence {confidence:.0%}."
        )

    return {
        "should_add_account_now": should_add,
        "platform": platform,
        "niche": brand_niche,
        "sub_niche": brand_sub_niche or best_next.get("niche_suggestion"),
        "account_type": account_type,
        "content_role": content_role,
        "monetization_path": monetization_path,
        "expected_upside": round(upside_monthly, 2),
        "expected_cost": cost_estimate,
        "expected_time_to_signal_days": time_to_signal,
        "confidence": confidence,
        "urgency": urgency,
        "explanation": explanation,
        "hold_reason": hold_reason,
        "blockers": blockers,
        "evidence": {
            "recommendation_key": rec_key,
            "incremental_profit_new": inc_new,
            "incremental_profit_existing": inc_exist,
            "scale_readiness": readiness,
            "expansion_confidence": exp_conf,
            "cannibalization_risk": cann,
            "audience_segment_separation": seg_sep,
            "account_count": len(accounts),
            "offer_count": offer_count,
            "content_count": content_count,
            "avg_health": avg_account_health,
            "avg_fatigue": avg_fatigue,
            "avg_saturation": avg_saturation,
        },
    }
