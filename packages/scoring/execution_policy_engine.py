"""Execution policy engine — decide autonomous vs guarded vs manual per action.

Pure functions only (no I/O, no SQLAlchemy). All logic deterministic.
"""
from __future__ import annotations

from typing import Any

EPE = "execution_policy_engine"

EXECUTION_MODES = ["autonomous", "guarded", "manual"]

ACTION_TYPES = [
    "publish_content",
    "create_derivative",
    "schedule_publish",
    "select_monetization",
    "suppress_lane",
    "pause_account",
    "increase_output",
    "decrease_output",
    "split_account",
    "trigger_follow_up",
    "send_notification",
    "create_content_brief",
    "queue_item_promotion",
    "distribution_plan_execute",
]

RISK_LEVELS = ["low", "medium", "high", "critical"]
COST_CLASSES = ["free", "low", "medium", "high"]
KILL_SWITCH_CLASSES = ["none", "soft", "hard", "emergency"]

_ACTION_RISK_MAP: dict[str, str] = {
    "publish_content": "medium",
    "create_derivative": "low",
    "schedule_publish": "medium",
    "select_monetization": "low",
    "suppress_lane": "medium",
    "pause_account": "high",
    "increase_output": "medium",
    "decrease_output": "low",
    "split_account": "high",
    "trigger_follow_up": "low",
    "send_notification": "low",
    "create_content_brief": "low",
    "queue_item_promotion": "low",
    "distribution_plan_execute": "medium",
}

_ACTION_COST_MAP: dict[str, str] = {
    "publish_content": "medium",
    "create_derivative": "low",
    "schedule_publish": "low",
    "select_monetization": "free",
    "suppress_lane": "free",
    "pause_account": "free",
    "increase_output": "medium",
    "decrease_output": "free",
    "split_account": "high",
    "trigger_follow_up": "low",
    "send_notification": "free",
    "create_content_brief": "low",
    "queue_item_promotion": "free",
    "distribution_plan_execute": "medium",
}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def compute_execution_policy(
    action_type: str,
    confidence: float,
    account_health: float,
    brand_context: dict[str, Any],
) -> dict[str, Any]:
    """Determine execution mode for an action based on risk, cost, confidence, and context.

    Parameters
    ----------
    action_type:
        One of ACTION_TYPES.
    confidence:
        Confidence in the action (0-1).
    account_health:
        Health of the target account (0-1).
    brand_context:
        Brand configuration. Expected keys:
        default_mode (str), compliance_level (str), budget_remaining (float),
        platform_sensitivity (str), has_active_violations (bool).

    Returns
    -------
    dict with execution_mode, approval_requirement, rollback_rule,
    kill_switch_class, risk_level, cost_class, explanation.
    """
    confidence = _clamp(confidence)
    account_health = _clamp(account_health)

    risk = _ACTION_RISK_MAP.get(action_type, "medium")
    cost = _ACTION_COST_MAP.get(action_type, "low")
    compliance = str(brand_context.get("compliance_level", "standard"))
    platform_sens = str(brand_context.get("platform_sensitivity", "standard"))
    has_violations = bool(brand_context.get("has_active_violations", False))
    default_mode = str(brand_context.get("default_mode", "guarded"))
    budget_remaining = float(brand_context.get("budget_remaining", 1000.0))

    risk_score = {"low": 0.2, "medium": 0.5, "high": 0.75, "critical": 1.0}.get(risk, 0.5)
    cost_score = {"free": 0.0, "low": 0.2, "medium": 0.5, "high": 0.8}.get(cost, 0.3)

    if has_violations:
        risk_score = min(1.0, risk_score + 0.25)
    if compliance in ("strict", "regulated"):
        risk_score = min(1.0, risk_score + 0.15)
    if platform_sens == "high":
        risk_score = min(1.0, risk_score + 0.1)
    if budget_remaining < 50 and cost_score > 0.3:
        risk_score = min(1.0, risk_score + 0.15)

    health_penalty = max(0.0, (0.5 - account_health) * 0.3)
    risk_score = min(1.0, risk_score + health_penalty)

    composite = confidence * 0.4 - risk_score * 0.35 - cost_score * 0.15 + account_health * 0.1

    if composite >= 0.25 and confidence >= 0.7 and risk_score < 0.6:
        mode = "autonomous"
    elif composite >= 0.05 or (confidence >= 0.5 and risk_score < 0.8):
        mode = "guarded"
    else:
        mode = "manual"

    if default_mode == "manual":
        mode = "manual"
    elif default_mode == "guarded" and mode == "autonomous":
        mode = "guarded"

    approval = "none"
    if mode == "manual":
        approval = "operator_required"
    elif mode == "guarded" and risk_score >= 0.6:
        approval = "operator_review"
    elif action_type in ("split_account", "pause_account"):
        approval = "operator_review"

    if risk_score >= 0.75:
        kill_switch = "hard"
    elif risk_score >= 0.5:
        kill_switch = "soft"
    else:
        kill_switch = "none"

    if action_type in ("pause_account", "split_account"):
        rollback = f"Revert {action_type} within 24h if health degrades further."
    elif action_type == "publish_content":
        rollback = "Unpublish within 1h if engagement < 0.1% or flagged."
    elif action_type == "suppress_lane":
        rollback = "Re-enable lane after lift conditions met."
    else:
        rollback = None

    budget_impact = "none"
    if cost in ("medium", "high"):
        budget_impact = "moderate" if budget_remaining > 200 else "high"

    explanation = (
        f"Action '{action_type}': mode={mode}, risk={risk} ({risk_score:.2f}), "
        f"cost={cost}, confidence={confidence:.2f}, health={account_health:.2f}. "
        f"Approval: {approval}. Kill-switch: {kill_switch}."
    )

    return {
        "action_type": action_type,
        "execution_mode": mode,
        "confidence_threshold": round(confidence, 4),
        "risk_level": risk,
        "risk_score": round(risk_score, 4),
        "cost_class": cost,
        "compliance_sensitivity": compliance,
        "platform_sensitivity": platform_sens,
        "budget_impact": budget_impact,
        "account_health_impact": "negative" if account_health < 0.4 else "neutral",
        "approval_requirement": approval,
        "rollback_rule": rollback,
        "kill_switch_class": kill_switch,
        "explanation": explanation,
        EPE: True,
    }


def compute_policies_for_brand(
    action_types: list[str],
    confidence_map: dict[str, float],
    account_health: float,
    brand_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compute policies for multiple action types at once."""
    policies = []
    for at in action_types:
        conf = confidence_map.get(at, 0.5)
        policies.append(compute_execution_policy(at, conf, account_health, brand_context))
    return policies


MONETIZATION_ROUTES = [
    "affiliate",
    "owned_product",
    "lead_gen",
    "booked_calls",
    "services",
    "high_ticket",
    "sponsors",
    "newsletter_media",
    "recurring_subscription",
    "community",
    "live_events",
    "ugc_creative_services",
    "licensing",
    "premium_access",
    "data_products",
    "syndication",
    "merch_physical",
    "affiliate_program_owned",
]

ROUTE_CLASSES = ["direct_sale", "lead_capture", "partnership", "passive_income", "recurring"]

_ROUTE_CLASS_MAP: dict[str, str] = {
    "affiliate": "partnership",
    "owned_product": "direct_sale",
    "lead_gen": "lead_capture",
    "booked_calls": "direct_sale",
    "services": "direct_sale",
    "high_ticket": "direct_sale",
    "sponsors": "partnership",
    "newsletter_media": "recurring",
    "recurring_subscription": "recurring",
    "community": "recurring",
    "live_events": "direct_sale",
    "ugc_creative_services": "direct_sale",
    "licensing": "passive_income",
    "premium_access": "recurring",
    "data_products": "passive_income",
    "syndication": "passive_income",
    "merch_physical": "direct_sale",
    "affiliate_program_owned": "partnership",
}

_ROUTE_FUNNEL: dict[str, str] = {
    "affiliate": "content → link → merchant checkout",
    "owned_product": "content → landing page → cart → checkout",
    "lead_gen": "content → opt-in → nurture → offer",
    "booked_calls": "content → calendar link → discovery call → close",
    "services": "content → inquiry → proposal → contract",
    "high_ticket": "content → application → call → close",
    "sponsors": "content → audience proof → pitch → deal",
    "newsletter_media": "content → subscribe → nurture → monetize",
    "recurring_subscription": "content → trial → subscribe → retain",
    "community": "content → join → engage → upsell",
    "live_events": "content → register → attend → offer",
    "ugc_creative_services": "content → portfolio → inquiry → contract",
    "licensing": "content → catalog → license agreement → royalty",
    "premium_access": "content → preview → subscribe → retain",
    "data_products": "content → sample → purchase → access",
    "syndication": "content → distribution deal → royalty",
    "merch_physical": "content → store → cart → ship",
    "affiliate_program_owned": "content → program page → sign-up → promote",
}

_ROUTE_FOLLOW_UPS: dict[str, list[str]] = {
    "affiliate": ["track_clicks", "monitor_conversions", "optimize_placement"],
    "owned_product": ["send_receipt", "onboard_customer", "request_review"],
    "lead_gen": ["send_lead_magnet", "start_email_sequence", "score_lead"],
    "booked_calls": ["send_confirmation", "send_reminder", "follow_up_no_show"],
    "services": ["send_proposal", "follow_up_72h", "contract_signing"],
    "high_ticket": ["send_application_review", "schedule_call", "send_offer"],
    "sponsors": ["send_media_kit", "negotiate_terms", "create_branded_content"],
    "newsletter_media": ["confirm_subscribe", "welcome_sequence", "segment_audience"],
    "recurring_subscription": ["trial_onboard", "engagement_check_7d", "renewal_reminder"],
    "community": ["welcome_member", "activation_challenge", "upsell_offer"],
    "live_events": ["send_ticket", "pre_event_content", "post_event_offer"],
    "ugc_creative_services": ["send_brief", "review_draft", "deliver_final"],
    "licensing": ["send_agreement", "deliver_assets", "track_royalties"],
    "premium_access": ["grant_access", "engagement_monitor", "retention_offer"],
    "data_products": ["deliver_access", "usage_monitor", "upsell_premium"],
    "syndication": ["deliver_content", "track_distribution", "collect_royalty"],
    "merch_physical": ["confirm_order", "ship_tracking", "review_request"],
    "affiliate_program_owned": ["approve_affiliate", "provide_assets", "track_performance"],
}


def select_monetization_route(
    content_context: dict[str, Any],
    brand_offers: list[dict[str, Any]],
    audience_signals: dict[str, Any],
    account_context: dict[str, Any],
) -> dict[str, Any]:
    """Select the best monetization route for a piece of content.

    Parameters
    ----------
    content_context:
        Dict with: content_family (str), niche (str), signal_type (str),
        monetization_path_hint (str, optional), urgency (float).
    brand_offers:
        List of offer dicts: name, type, keywords, revenue_per_conversion, active (bool).
    audience_signals:
        Dict with: conversion_intent (float 0-1), engagement_rate (float),
        email_list_size (int), community_size (int), follower_count (int).
    account_context:
        Dict with: platform (str), maturity_state (str), health_score (float).

    Returns
    -------
    dict with selected_route, route_class, funnel_path, follow_up_requirements,
    revenue_estimate, confidence, explanation.
    """
    hint = str(content_context.get("monetization_path_hint", ""))
    content_family = str(content_context.get("content_family", "general"))
    niche = str(content_context.get("niche", ""))
    urgency = _clamp(float(content_context.get("urgency", 0.5)))

    conversion_intent = _clamp(float(audience_signals.get("conversion_intent", 0.3)))
    engagement_rate = float(audience_signals.get("engagement_rate", 0.02))
    email_list = int(audience_signals.get("email_list_size", 0))
    community_size = int(audience_signals.get("community_size", 0))
    follower_count = int(audience_signals.get("follower_count", 0))

    platform = str(account_context.get("platform", "youtube"))
    maturity = str(account_context.get("maturity_state", "stable"))
    health = _clamp(float(account_context.get("health_score", 0.5)))

    active_offers = [o for o in brand_offers if o.get("active", True)]
    has_products = any(o.get("type") in ("digital_product", "course", "saas", "physical") for o in active_offers)
    has_services = any(o.get("type") in ("service", "consulting", "coaching") for o in active_offers)
    has_sponsors = any(o.get("type") in ("sponsor", "brand_deal") for o in active_offers)

    scores: dict[str, float] = {}

    for route in MONETIZATION_ROUTES:
        score = 0.3

        if hint and route == hint:
            score += 0.25

        if route == "affiliate":
            score += conversion_intent * 0.2 + (0.15 if content_family == "review_comparison" else 0)
        elif route == "owned_product" and has_products:
            score += conversion_intent * 0.25 + (0.2 if content_family == "conversion_content" else 0)
        elif route == "lead_gen":
            score += (0.2 if email_list > 100 else 0.05) + (0.15 if content_family == "trust_building" else 0)
        elif route == "booked_calls" and has_services:
            score += conversion_intent * 0.2 + (0.15 if content_family == "authority_piece" else 0)
        elif route == "services" and has_services:
            score += 0.15 + (0.1 if content_family in ("authority_piece", "differentiation") else 0)
        elif route == "high_ticket" and has_services:
            score += conversion_intent * 0.3 if conversion_intent > 0.6 else 0
        elif route == "sponsors" and has_sponsors:
            score += 0.2 + (0.15 if follower_count > 5000 else 0)
        elif route == "newsletter_media":
            score += 0.1 + (0.15 if email_list > 500 else 0)
        elif route == "recurring_subscription":
            score += 0.15 if community_size > 50 else 0
        elif route == "community":
            score += 0.1 + (0.1 if community_size > 100 else 0)
        elif route == "live_events":
            score += 0.1 if follower_count > 1000 else 0
        elif route == "merch_physical":
            score += 0.1 if follower_count > 5000 else 0
        elif route == "licensing":
            score += 0.05
        elif route == "premium_access":
            score += 0.1 if content_family == "evergreen_series" else 0
        elif route == "syndication":
            score += 0.05
        elif route == "data_products":
            score += 0.05

        if maturity in ("newborn", "warming"):
            if route in ("high_ticket", "sponsors", "licensing", "syndication"):
                score *= 0.3
        if health < 0.4:
            score *= 0.7

        scores[route] = round(score, 4)

    best_route = max(scores, key=lambda k: scores[k])
    best_score = scores[best_route]

    route_class = _ROUTE_CLASS_MAP.get(best_route, "direct_sale")
    funnel_path = _ROUTE_FUNNEL.get(best_route, "content → action")
    follow_ups = _ROUTE_FOLLOW_UPS.get(best_route, [])

    avg_rev = 0.0
    for o in active_offers:
        avg_rev += float(o.get("revenue_per_conversion", 0))
    if active_offers:
        avg_rev /= len(active_offers)

    revenue_mult = {"direct_sale": 1.0, "lead_capture": 0.3, "partnership": 0.5, "passive_income": 0.2, "recurring": 0.8}
    revenue_est = round(avg_rev * revenue_mult.get(route_class, 0.5) * conversion_intent * 10, 2)

    confidence = round(_clamp(best_score * 0.6 + health * 0.2 + conversion_intent * 0.2), 4)

    explanation = (
        f"Selected '{best_route}' (class: {route_class}) with confidence {confidence:.2f}. "
        f"Funnel: {funnel_path}. "
        f"Content family '{content_family}', platform '{platform}', maturity '{maturity}'. "
        f"Revenue estimate: ${revenue_est:.2f}."
    )

    return {
        "selected_route": best_route,
        "route_class": route_class,
        "funnel_path": funnel_path,
        "follow_up_requirements": follow_ups,
        "revenue_estimate": revenue_est,
        "confidence": confidence,
        "route_scores": scores,
        "explanation": explanation,
        EPE: True,
    }


SUPPRESSION_TYPES = [
    "pause_lane",
    "reduce_output",
    "suppress_queue_item",
    "suppress_content_family",
    "suppress_account_expansion",
    "suppress_monetization_path",
]


def evaluate_suppressions(
    accounts: list[dict[str, Any]],
    queue_items: list[dict[str, Any]],
    performance: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate which lanes, queue items, or content families should be suppressed.

    Parameters
    ----------
    accounts:
        List of account dicts: account_id, platform, maturity_state, health_score,
        saturation_score, avg_engagement_rate, current_output_per_week.
    queue_items:
        List of queue item dicts: id, content_family, platform, priority_score,
        monetization_path, queue_status.
    performance:
        Brand-level metrics: overall_engagement_rate (float), revenue_trend (str: up/flat/down),
        content_fatigue_score (float 0-1), audience_growth_rate (float).

    Returns
    -------
    list[dict] — each with suppression_type, affected_scope, trigger_reason,
    duration_hours, lift_condition, confidence, explanation.
    """
    suppressions: list[dict[str, Any]] = []
    fatigue = float(performance.get("content_fatigue_score", 0))
    revenue_trend = str(performance.get("revenue_trend", "flat"))
    overall_eng = float(performance.get("overall_engagement_rate", 0.02))

    for acct in accounts:
        health = float(acct.get("health_score", 0.5))
        saturation = float(acct.get("saturation_score", 0))
        maturity = acct.get("maturity_state", "stable")
        output = int(acct.get("current_output_per_week", 0))

        if health < 0.25 and output > 3:
            suppressions.append({
                "suppression_type": "pause_lane",
                "affected_scope": f"account:{acct.get('account_id')}",
                "affected_entity_id": acct.get("account_id"),
                "trigger_reason": f"Account health critically low ({health:.2f}). Output {output}/wk needs pause.",
                "duration_hours": 168,
                "lift_condition": "health_score >= 0.4",
                "confidence": round(_clamp(0.85 - health * 0.3), 4),
                "explanation": f"Pausing account {acct.get('account_id')} due to low health ({health:.2f}).",
                EPE: True,
            })

        if saturation > 0.8 and output > 5:
            new_output = max(3, int(output * 0.6))
            suppressions.append({
                "suppression_type": "reduce_output",
                "affected_scope": f"account:{acct.get('account_id')}",
                "affected_entity_id": acct.get("account_id"),
                "trigger_reason": f"Saturation {saturation:.2f} — reducing from {output} to {new_output}/wk.",
                "duration_hours": 336,
                "lift_condition": "saturation_score < 0.5",
                "confidence": round(_clamp(0.6 + saturation * 0.3), 4),
                "explanation": f"Reducing output for saturated account {acct.get('account_id')}.",
                EPE: True,
            })

        if maturity in ("at_risk", "cooling") and output > 3:
            suppressions.append({
                "suppression_type": "suppress_account_expansion",
                "affected_scope": f"account:{acct.get('account_id')}",
                "affected_entity_id": acct.get("account_id"),
                "trigger_reason": f"Account maturity '{maturity}' — blocking expansion.",
                "duration_hours": None,
                "lift_condition": f"maturity_state in ('stable', 'scaling')",
                "confidence": 0.80,
                "explanation": f"Blocking expansion for {maturity} account.",
                EPE: True,
            })

    family_perf: dict[str, list[float]] = {}
    for qi in queue_items:
        fam = qi.get("content_family", "general")
        prio = float(qi.get("priority_score", 0))
        family_perf.setdefault(fam, []).append(prio)

    for fam, prios in family_perf.items():
        avg_prio = sum(prios) / len(prios) if prios else 0
        if avg_prio < 0.2 and fatigue > 0.6:
            suppressions.append({
                "suppression_type": "suppress_content_family",
                "affected_scope": f"content_family:{fam}",
                "affected_entity_id": None,
                "trigger_reason": f"Content family '{fam}' avg priority {avg_prio:.2f} with fatigue {fatigue:.2f}.",
                "duration_hours": 168,
                "lift_condition": "content_fatigue_score < 0.3",
                "confidence": round(_clamp(fatigue * 0.7 + (1.0 - avg_prio) * 0.3), 4),
                "explanation": f"Suppressing weak content family '{fam}'.",
                EPE: True,
            })

    if revenue_trend == "down" and overall_eng < 0.015:
        suppressions.append({
            "suppression_type": "suppress_monetization_path",
            "affected_scope": "brand:monetization_aggressive",
            "affected_entity_id": None,
            "trigger_reason": f"Revenue trending down with low engagement ({overall_eng:.3f}).",
            "duration_hours": 336,
            "lift_condition": "revenue_trend != 'down' and engagement_rate >= 0.02",
            "confidence": 0.70,
            "explanation": "Suppressing aggressive monetization paths during downturn.",
            EPE: True,
        })

    return suppressions


RUN_STEPS = [
    "queued",
    "policy_check",
    "content_brief_creation",
    "content_generation",
    "derivative_creation",
    "distribution_planning",
    "monetization_routing",
    "publish_queued",
    "publishing",
    "follow_up",
    "monitoring",
    "completed",
]

RUN_STATUSES = ["pending", "running", "paused", "completed", "failed", "cancelled"]

DISTRIBUTION_DERIVATIVE_TYPES = [
    "short_clip",
    "carousel",
    "thread",
    "blog_post",
    "newsletter_segment",
    "story",
    "reel",
    "static_image",
    "quote_card",
    "audio_snippet",
]


def plan_distribution(
    source_concept: str,
    source_platform: str,
    content_family: str,
    available_accounts: list[dict[str, Any]],
    platform_policies: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a cross-platform distribution plan for a content concept.

    Parameters
    ----------
    source_concept:
        Title/description of the source content.
    source_platform:
        Platform where the original content will be published.
    content_family:
        Content family classification (e.g., trend_response, authority_piece).
    available_accounts:
        List of account dicts: account_id, platform, maturity_state, health_score,
        current_output_per_week, max_safe_output_per_week.
    platform_policies:
        List of platform policy dicts: platform, max_safe_output_per_day.

    Returns
    -------
    dict with target_platforms, derivative_types, platform_priority,
    cadence, publish_timing, duplication_guard, confidence, explanation.
    """
    policy_by_platform = {p.get("platform", ""): p for p in platform_policies}

    _DERIVATIVE_MAP: dict[str, list[str]] = {
        "youtube": ["short_clip", "blog_post", "newsletter_segment", "quote_card"],
        "tiktok": ["short_clip", "story", "reel"],
        "instagram": ["reel", "carousel", "story", "static_image"],
        "twitter": ["thread", "quote_card", "static_image"],
        "linkedin": ["blog_post", "carousel", "static_image"],
        "reddit": ["blog_post", "thread"],
        "facebook": ["short_clip", "story", "static_image", "carousel"],
    }

    target_platforms: list[dict[str, Any]] = []
    seen_platforms = set()

    for acct in available_accounts:
        plat = acct.get("platform", "")
        if plat == source_platform or plat in seen_platforms:
            continue

        health = float(acct.get("health_score", 0.5))
        maturity = acct.get("maturity_state", "stable")
        current_out = int(acct.get("current_output_per_week", 0))
        max_out = int(acct.get("max_safe_output_per_week", 21))

        if health < 0.3 or maturity in ("at_risk", "newborn"):
            continue
        if current_out >= max_out:
            continue

        derivatives = _DERIVATIVE_MAP.get(plat, ["static_image", "quote_card"])

        priority = 0.5
        if maturity in ("stable", "scaling"):
            priority += 0.2
        if health >= 0.7:
            priority += 0.15
        headroom = (max_out - current_out) / max(max_out, 1)
        priority += headroom * 0.15

        target_platforms.append({
            "platform": plat,
            "account_id": acct.get("account_id"),
            "derivatives": derivatives[:3],
            "priority": round(priority, 4),
            "headroom": round(headroom, 4),
        })
        seen_platforms.add(plat)

    target_platforms.sort(key=lambda t: t["priority"], reverse=True)

    all_derivatives = set()
    for t in target_platforms:
        for d in t["derivatives"]:
            all_derivatives.add(d)

    cadence: dict[str, Any] = {}
    for t in target_platforms:
        plat = t["platform"]
        pol = policy_by_platform.get(plat, {})
        max_daily = int(pol.get("max_safe_output_per_day", 3))
        cadence[plat] = {
            "delay_hours_from_source": 24 + len(cadence) * 12,
            "max_per_day": max_daily,
        }

    duplication_guard = {
        "max_platforms_per_concept": min(5, len(target_platforms)),
        "min_delay_between_platforms_hours": 12,
        "max_derivatives_per_platform": 3,
    }

    publish_timing: dict[str, str] = {}
    for i, t in enumerate(target_platforms):
        delay = cadence.get(t["platform"], {}).get("delay_hours_from_source", 24)
        publish_timing[t["platform"]] = f"+{delay}h from source publish"

    confidence = round(_clamp(0.5 + len(target_platforms) * 0.08), 4)

    explanation = (
        f"Distribution plan for '{source_concept}' from {source_platform}. "
        f"{len(target_platforms)} target platforms, {len(all_derivatives)} derivative types. "
        f"Cadence staggered to avoid duplication overload."
    )

    return {
        "source_concept": source_concept,
        "source_platform": source_platform,
        "content_family": content_family,
        "target_platforms": target_platforms,
        "derivative_types": sorted(all_derivatives),
        "platform_priority": {t["platform"]: t["priority"] for t in target_platforms},
        "cadence": cadence,
        "publish_timing": publish_timing,
        "duplication_guard": duplication_guard,
        "confidence": confidence,
        "explanation": explanation,
        EPE: True,
    }
