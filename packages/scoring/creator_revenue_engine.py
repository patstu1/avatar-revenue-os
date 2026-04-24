"""Creator Revenue Avenues — Phase A engine logic."""
from __future__ import annotations

from typing import Any


def _avg_payout(ctx: dict) -> float:
    """Extract avg_payout from brand context, default to 1000 if not provided."""
    return ctx.get("avg_payout", 1000)

UGC_SERVICE_TYPES = [
    "ugc_content_production",
    "ad_creative_production",
    "short_form_content_packages",
    "spokesperson_avatar_services",
    "editing_repurposing_packages",
    "campaign_creative_packages",
    "platform_native_creative_bundles",
]

CONSULTING_SERVICE_TYPES = [
    "strategic_advisory",
    "implementation_services",
    "content_strategy_consulting",
    "automation_consulting",
    "done_for_you_setups",
    "audits_roadmaps",
    "premium_workshops",
    "retained_support",
]

PREMIUM_ACCESS_TYPES = [
    "premium_membership",
    "vip_concierge",
    "priority_advisory",
    "exclusive_guidance",
    "inner_circle",
]

LICENSING_TYPES = [
    "creative_asset_licensing",
    "content_format_licensing",
    "workflow_system_licensing",
    "ip_package_licensing",
    "white_label_rights",
    "limited_use_licensing",
]

SYNDICATION_TYPES = [
    "cross_channel_syndication",
    "content_package_syndication",
    "media_newsletter_syndication",
    "republishing_rights",
    "partner_distribution_bundles",
]

DATA_PRODUCT_TYPES = [
    "niche_database",
    "premium_intelligence_feed",
    "swipe_file",
    "research_pack",
    "signal_trend_dataset",
    "premium_reporting_product",
]

MERCH_TYPES = [
    "creator_branded_drop",
    "evergreen_store_product",
    "product_line_experiment",
    "physical_bundle",
    "limited_edition_release",
]

LIVE_EVENT_TYPES = [
    "webinar",
    "workshop",
    "live_creator_session",
    "paid_live_event",
    "premium_qa_office_hours",
    "niche_event_product",
]

AFFILIATE_PROGRAM_TYPES = [
    "affiliate_recruitment",
    "affiliate_program_launch",
    "incentive_model_optimization",
    "partner_tier_expansion",
    "affiliate_attribution_setup",
]

AVENUE_TYPES = [
    "ugc_services", "consulting", "premium_access",
    "licensing", "syndication", "data_products",
    "merch", "live_events", "owned_affiliate_program",
]

PRICE_BANDS = {
    "low": (100, 500),
    "mid": (500, 2500),
    "high": (2500, 10000),
    "premium": (10000, 50000),
}


def score_ugc_opportunity(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate UGC/creative service opportunities based on brand context."""
    results: list[dict[str, Any]] = []
    audience_size = brand_ctx.get("audience_size", 0)
    content_count = brand_ctx.get("content_count", 0)
    niche = brand_ctx.get("niche", "general")
    has_avatar = brand_ctx.get("has_avatar", False)
    account_count = brand_ctx.get("account_count", 0)
    avg_payout = brand_ctx.get("avg_payout", 1000)  # Dynamic from portfolio, default 1000

    # Dynamic: confidence based on relative content and audience, not fixed divisors
    base_confidence = min(0.9, 0.3 + min(content_count / max(content_count + 1, 1), 0.2) * 0.2 + min(audience_size / max(audience_size + 1, 1), 0.2) * 0.2)
    if content_count > 0 and audience_size > 0:
        base_confidence = max(base_confidence, 0.5)  # Any portfolio with content + audience gets 0.5 floor

    for stype in UGC_SERVICE_TYPES:
        conf = base_confidence
        value = 0.0
        margin = 0.0
        segment = "small_business"
        package = ""
        steps: list[str] = []

        if stype == "ugc_content_production":
            # Value scales with audience — no fixed ceiling
            value = max(750, audience_size * 0.03) if audience_size > 0 else 750
            margin = value * 0.7
            segment = "ecommerce_brands" if audience_size > content_count * 100 else "local_businesses"
            package = f"UGC {niche} content pack — 5 pieces"
            steps = ["Identify target brands", "Create portfolio samples", "Set pricing", "Outreach", "Deliver"]
            conf = min(0.85, conf + 0.1) if content_count > 10 else conf

        elif stype == "ad_creative_production":
            value = 2500 if has_avatar else 1000
            margin = value * 0.65
            segment = "dtc_brands"
            package = "Ad creative bundle — 3 hooks × 2 variants"
            steps = ["Script ad hooks", "Produce variants", "Deliver with usage rights"]
            conf = min(0.8, conf + 0.15) if has_avatar else conf * 0.7

        elif stype == "short_form_content_packages":
            value = 2000
            margin = value * 0.75
            segment = "saas_startups" if niche in ("tech", "saas", "software") else "consumer_brands"
            package = f"10× short-form {niche} videos/month"
            steps = ["Content calendar", "Batch produce", "Edit + caption", "Deliver monthly"]
            conf = min(0.8, conf + 0.1) if content_count > 20 else conf

        elif stype == "spokesperson_avatar_services":
            if not has_avatar:
                conf *= 0.3
            value = 5000 if has_avatar else 500
            margin = value * 0.8
            segment = "enterprise_brands"
            package = "AI spokesperson package — custom avatar + 10 scripts"
            steps = ["Avatar setup", "Script development", "Production", "Brand approval", "Deliver"]

        elif stype == "editing_repurposing_packages":
            value = 800
            margin = value * 0.8
            segment = "creators_and_coaches"
            package = "Monthly repurposing — long-form → 20 clips"
            steps = ["Receive source content", "Clip selection", "Edit + resize", "Deliver"]
            conf = min(0.85, conf + 0.05)

        elif stype == "campaign_creative_packages":
            value = 3500
            margin = value * 0.6
            segment = "agencies"
            package = f"Full campaign creative for {niche}"
            steps = ["Strategy brief", "Concept development", "Multi-format production", "Revisions", "Deliver"]
            conf *= 0.9 if account_count >= 3 else 0.6

        elif stype == "platform_native_creative_bundles":
            value = 1800
            margin = value * 0.7
            segment = "platform_advertisers"
            package = "Platform-native bundle — TikTok + Reels + Shorts"
            steps = ["Platform audit", "Native format production", "Platform optimization", "Deliver"]
            conf = min(0.8, conf + 0.05) if account_count >= 2 else conf * 0.7

        if conf >= 0.2:
            results.append({
                "service_type": stype,
                "target_segment": segment,
                "recommended_package": package,
                "price_band": "high" if value > avg_payout else "mid" if value > avg_payout * 0.3 else "low",
                "expected_value": round(value, 2),
                "expected_margin": round(margin, 2),
                "execution_steps": steps,
                "confidence": round(conf, 3),
                "explanation": f"{stype.replace('_', ' ').title()} for {segment} — est. ${value:.0f} at {conf:.0%} confidence",
            })

    return sorted(results, key=lambda r: r["expected_value"] * r["confidence"], reverse=True)


def score_consulting_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    niche = brand_ctx.get("niche", "general")
    brand_ctx.get("audience_size", 0)
    content_count = brand_ctx.get("content_count", 0)
    offer_count = brand_ctx.get("offer_count", 0)

    avg_payout = _avg_payout(brand_ctx)
    base_confidence = min(0.8, 0.25 + (content_count / 30) * 0.15 + (offer_count / 5) * 0.15)

    service_configs = [
        ("strategic_advisory", "premium", "founders_ceos", 5000, 0.85,
         ["Discovery call", "Audit", "Strategy document", "Implementation roadmap", "Follow-up"]),
        ("implementation_services", "standard", "marketing_teams", 3000, 0.7,
         ["Scope project", "Setup systems", "Configure automations", "Train team", "Handoff"]),
        ("content_strategy_consulting", "standard", "creators_and_brands", 2000, 0.75,
         ["Content audit", "Strategy session", "Calendar build", "Template creation", "Review cycle"]),
        ("automation_consulting", "standard", "operations_teams", 3500, 0.65,
         ["Process audit", "Automation design", "Tool selection", "Implementation", "Documentation"]),
        ("done_for_you_setups", "standard", "solopreneurs", 1500, 0.7,
         ["Requirements gathering", "System setup", "Content migration", "Testing", "Launch"]),
        ("audits_roadmaps", "entry", "startups", 1000, 0.8,
         ["Collect data", "Analyze performance", "Identify gaps", "Build roadmap", "Present findings"]),
        ("premium_workshops", "premium", "teams_and_cohorts", 4000, 0.6,
         ["Design curriculum", "Prepare materials", "Deliver workshop", "Q&A", "Follow-up resources"]),
        ("retained_support", "premium", "enterprise_clients", 8000, 0.5,
         ["Contract negotiation", "Onboarding", "Monthly strategy calls", "Async support", "Quarterly review"]),
    ]

    for stype, tier, buyer, value, conf_mult, steps in service_configs:
        conf = round(min(0.9, base_confidence * conf_mult), 3)
        if niche in ("tech", "saas", "finance", "business"):
            conf = min(0.9, conf + 0.05)
            value = int(value * 1.2)

        if conf >= 0.15:
            results.append({
                "service_type": stype,
                "service_tier": tier,
                "target_buyer": buyer,
                "price_band": "premium" if value > avg_payout * 3 else "high" if value > avg_payout else "mid",
                "expected_deal_value": round(float(value), 2),
                "execution_plan": steps,
                "confidence": conf,
                "explanation": f"{stype.replace('_', ' ').title()} ({tier}) for {buyer} — est. ${value:.0f}",
            })

    return sorted(results, key=lambda r: r["expected_deal_value"] * r["confidence"], reverse=True)


def score_premium_access_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    audience_size = brand_ctx.get("audience_size", 0)
    brand_ctx.get("niche", "general")
    offer_count = brand_ctx.get("offer_count", 0)
    has_community = brand_ctx.get("has_community", False)

    base_confidence = min(0.75, 0.2 + (audience_size / 20000) * 0.2 + (offer_count / 5) * 0.15)

    access_configs = [
        ("premium_membership", "loyal_audience", "Minimum 3 months active engagement", "recurring", 49, 0.8,
         ["Design membership tiers", "Build access portal", "Create onboarding", "Launch", "Retain"]),
        ("vip_concierge", "high_value_clients", "Previous purchase > $500", "one_time", 2500, 0.5,
         ["Identify VIP candidates", "Design concierge package", "Personal outreach", "Onboard", "Deliver"]),
        ("priority_advisory", "decision_makers", "Company revenue > $1M", "recurring", 500, 0.6,
         ["Qualify leads", "Schedule discovery", "Propose advisory terms", "Onboard", "Monthly sessions"]),
        ("exclusive_guidance", "aspiring_creators", "Application required", "recurring", 197, 0.7,
         ["Build application process", "Select cohort", "Design curriculum", "Deliver weekly", "Community"]),
        ("inner_circle", "top_1pct_audience", "Invitation only", "recurring", 997, 0.4,
         ["Identify top fans", "Design inner circle", "Personal invitations", "Exclusive content", "Direct access"]),
    ]

    for otype, segment, criteria, rev_model, value, conf_mult, steps in access_configs:
        conf = round(min(0.85, base_confidence * conf_mult), 3)
        if has_community:
            conf = min(0.85, conf + 0.1)
        if otype == "inner_circle" and audience_size < max(audience_size * 0.1, 1):
            conf *= 0.4

        monthly = value if rev_model == "recurring" else 0
        annual_est = monthly * 12 if rev_model == "recurring" else value

        if conf >= 0.1:
            results.append({
                "offer_type": otype,
                "target_segment": segment,
                "entry_criteria": criteria,
                "revenue_model": rev_model,
                "expected_value": round(float(annual_est), 2),
                "execution_plan": steps,
                "confidence": conf,
                "explanation": f"{otype.replace('_', ' ').title()} for {segment} — ${value}/{'mo' if rev_model == 'recurring' else 'one-time'} at {conf:.0%} confidence",
            })

    return sorted(results, key=lambda r: r["expected_value"] * r["confidence"], reverse=True)


def detect_creator_revenue_blockers(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    if brand_ctx.get("content_count", 0) < 5:
        blockers.append({
            "avenue_type": "ugc_services",
            "blocker_type": "insufficient_portfolio",
            "severity": "high",
            "description": "Fewer than 5 content items. UGC clients need portfolio proof.",
            "operator_action_needed": "Produce at least 5 sample content items to build a portfolio.",
        })
    if not brand_ctx.get("has_avatar"):
        blockers.append({
            "avenue_type": "ugc_services",
            "blocker_type": "no_avatar_configured",
            "severity": "medium",
            "description": "No avatar configured. Spokesperson/avatar services are limited.",
            "operator_action_needed": "Configure at least one AI avatar for spokesperson services.",
        })
    if brand_ctx.get("offer_count", 0) == 0:
        blockers.append({
            "avenue_type": "consulting",
            "blocker_type": "no_offers_defined",
            "severity": "high",
            "description": "No offers defined. Consulting credibility requires at least one live offer.",
            "operator_action_needed": "Create at least one offer in the Offer Catalog.",
        })
    if brand_ctx.get("audience_size", 0) < 1000:
        blockers.append({
            "avenue_type": "premium_access",
            "blocker_type": "audience_too_small",
            "severity": "medium",
            "description": "Audience under 1,000. Premium access tiers need sufficient audience.",
            "operator_action_needed": "Grow audience to at least 1,000 before launching premium access.",
        })
    if not brand_ctx.get("has_payment_processor"):
        blockers.append({
            "avenue_type": "all",
            "blocker_type": "no_payment_processor",
            "severity": "critical",
            "description": "No payment processor connected. Cannot collect revenue.",
            "operator_action_needed": "Connect Stripe, PayPal, or another payment processor.",
        })
    if not brand_ctx.get("has_landing_page"):
        blockers.append({
            "avenue_type": "all",
            "blocker_type": "no_landing_page",
            "severity": "medium",
            "description": "No landing page or service page configured.",
            "operator_action_needed": "Create a service landing page for inbound inquiries.",
        })
    return blockers


def _plan_to_opp(avenue_type: str, p: dict[str, Any], subtype_key: str, value_key: str, segment_key: str, margin_pct: float = 0.75) -> dict[str, Any]:
    val = p.get(value_key, 0)
    return {
        "avenue_type": avenue_type,
        "subtype": p.get(subtype_key, "unknown"),
        "target_segment": p.get(segment_key, "general"),
        "recommended_package": p.get("recommended_package") or f"{p.get(subtype_key, '').replace('_', ' ').title()}",
        "expected_value": val,
        "expected_margin": round(val * margin_pct, 2),
        "priority_score": round(val * p.get("confidence", 0) / 1000, 3),
        "confidence": p.get("confidence", 0),
        "explanation": p.get("explanation", ""),
    }


def build_revenue_opportunities(
    ugc_plans: list[dict[str, Any]],
    consulting_plans: list[dict[str, Any]],
    premium_plans: list[dict[str, Any]],
    licensing_plans: list[dict[str, Any]] | None = None,
    syndication_plans: list[dict[str, Any]] | None = None,
    data_product_plans: list[dict[str, Any]] | None = None,
    merch_plans: list[dict[str, Any]] | None = None,
    live_event_plans: list[dict[str, Any]] | None = None,
    affiliate_plans: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Consolidate all avenues into a unified opportunity list."""
    opps: list[dict[str, Any]] = []

    for p in ugc_plans:
        opps.append(_plan_to_opp("ugc_services", p, "service_type", "expected_value", "target_segment", 0.7))
        opps[-1]["recommended_package"] = p.get("recommended_package", "")
        opps[-1]["expected_margin"] = p.get("expected_margin", round(p["expected_value"] * 0.7, 2))

    for p in consulting_plans:
        opps.append(_plan_to_opp("consulting", p, "service_type", "expected_deal_value", "target_buyer", 0.8))
        opps[-1]["recommended_package"] = f"{p['service_type'].replace('_', ' ').title()} ({p['service_tier']})"

    for p in premium_plans:
        opps.append(_plan_to_opp("premium_access", p, "offer_type", "expected_value", "target_segment", 0.85))
        opps[-1]["recommended_package"] = f"{p['offer_type'].replace('_', ' ').title()} — {p['revenue_model']}"

    for p in (licensing_plans or []):
        opps.append(_plan_to_opp("licensing", p, "asset_type", "expected_deal_value", "target_buyer_type", 0.8))

    for p in (syndication_plans or []):
        opps.append(_plan_to_opp("syndication", p, "syndication_format", "expected_value", "target_partner", 0.75))

    for p in (data_product_plans or []):
        opps.append(_plan_to_opp("data_products", p, "product_type", "expected_value", "target_segment", 0.8))

    for p in (merch_plans or []):
        opps.append(_plan_to_opp("merch", p, "product_class", "expected_value", "target_segment", 0.5))

    for p in (live_event_plans or []):
        opps.append(_plan_to_opp("live_events", p, "event_type", "expected_value", "audience_segment", 0.7))

    for p in (affiliate_plans or []):
        opps.append(_plan_to_opp("owned_affiliate_program", p, "program_type", "expected_value", "target_partner_type", 0.6))

    return sorted(opps, key=lambda o: o["priority_score"], reverse=True)


# ── Phase B: Licensing ─────────────────────────────────────────────────


def score_licensing_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    content_count = brand_ctx.get("content_count", 0)
    has_avatar = brand_ctx.get("has_avatar", False)
    niche = brand_ctx.get("niche", "general")
    brand_ctx.get("offer_count", 0)
    brand_ctx.get("audience_size", 0)
    avg_payout = brand_ctx.get("avg_payout", 1000)

    base_confidence = min(0.75, 0.2 + (content_count / 40) * 0.2 + (0.1 if has_avatar else 0))

    licensing_configs = [
        ("creative_asset_licensing", "standard", "agencies_and_brands", "limited_use", 2000, 0.75,
         ["Catalog licensable assets", "Set usage tiers", "Create licensing agreement", "Publish catalog", "Fulfill"]),
        ("content_format_licensing", "standard", "content_teams", "limited_use", 1500, 0.65,
         ["Document format methodology", "Package templates", "Create licensing terms", "Distribute", "Support"]),
        ("workflow_system_licensing", "premium", "operations_teams", "full_use", 5000, 0.5,
         ["Document workflow IP", "Build licensable package", "Create onboarding", "Negotiate terms", "Deliver + support"]),
        ("ip_package_licensing", "premium", "enterprise_buyers", "full_use", 8000, 0.4,
         ["Identify licensable IP", "Legal review", "Package and price", "Outreach to buyers", "Execute agreement"]),
        ("white_label_rights", "premium", "resellers_and_agencies", "full_use", 10000, 0.35,
         ["Define white-label scope", "Remove branding", "Create partner terms", "Negotiate exclusivity", "Deliver"]),
        ("limited_use_licensing", "entry", "small_businesses", "limited_use", 500, 0.8,
         ["Select micro-assets", "Set limited terms", "Create self-serve checkout", "Automate delivery", "Track usage"]),
    ]

    for ltype, tier, buyer, scope, value, conf_mult, steps in licensing_configs:
        conf = round(min(0.85, base_confidence * conf_mult), 3)

        if niche in ("tech", "saas", "finance", "business"):
            conf = min(0.85, conf + 0.05)
            value = int(value * 1.15)

        if ltype in ("workflow_system_licensing", "ip_package_licensing", "white_label_rights"):
            if content_count < 20:
                conf *= 0.5
            if not has_avatar and ltype == "white_label_rights":
                conf *= 0.4

        if conf >= 0.1:
            results.append({
                "asset_type": ltype,
                "licensing_tier": tier,
                "target_buyer_type": buyer,
                "usage_scope": scope,
                "price_band": "premium" if value > avg_payout * 3 else "high" if value > avg_payout else "mid" if value > avg_payout * 0.3 else "low",
                "expected_deal_value": round(float(value), 2),
                "execution_plan": steps,
                "confidence": conf,
                "explanation": f"{ltype.replace('_', ' ').title()} ({scope}) for {buyer} — est. ${value:.0f}",
            })

    return sorted(results, key=lambda r: r["expected_deal_value"] * r["confidence"], reverse=True)


# ── Phase B: Syndication ───────────────────────────────────────────────


def score_syndication_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    content_count = brand_ctx.get("content_count", 0)
    brand_ctx.get("audience_size", 0)
    niche = brand_ctx.get("niche", "general")
    account_count = brand_ctx.get("account_count", 0)
    avg_payout = brand_ctx.get("avg_payout", 1000)

    base_confidence = min(0.7, 0.15 + (content_count / 30) * 0.2 + (account_count / 5) * 0.1)

    syndication_configs = [
        ("cross_channel_syndication", "platform_operators", "recurring", 800, 0.8,
         ["Identify cross-platform value", "Package content feed", "Negotiate distribution terms", "Automate delivery", "Monitor"]),
        ("content_package_syndication", "media_companies", "one_time", 3000, 0.55,
         ["Curate best-performing content", "Package with rights", "Pitch to media buyers", "Negotiate", "Deliver"]),
        ("media_newsletter_syndication", "newsletter_operators", "recurring", 500, 0.75,
         ["Identify newsletter partners", "Propose column or section", "Agree on cadence", "Deliver content", "Track metrics"]),
        ("republishing_rights", "publishers_and_blogs", "one_time", 1500, 0.6,
         ["Identify republish-worthy content", "Set republishing terms", "Outreach to publishers", "Execute agreement", "Track"]),
        ("partner_distribution_bundles", "distribution_partners", "recurring", 2000, 0.5,
         ["Design bundle offering", "Identify distribution partners", "Negotiate revenue share", "Integrate feeds", "Monitor"]),
    ]

    for sformat, partner, rev_model, value, conf_mult, steps in syndication_configs:
        conf = round(min(0.8, base_confidence * conf_mult), 3)

        if niche in ("tech", "finance", "business", "marketing"):
            conf = min(0.8, conf + 0.05)

        if content_count < 10:
            conf *= 0.5

        monthly = value if rev_model == "recurring" else 0
        annual_est = monthly * 12 if rev_model == "recurring" else value

        if conf >= 0.1:
            results.append({
                "syndication_format": sformat,
                "target_partner": partner,
                "revenue_model": rev_model,
                "price_band": "high" if annual_est > avg_payout else "mid" if annual_est > avg_payout * 0.3 else "low",
                "expected_value": round(float(annual_est), 2),
                "execution_plan": steps,
                "confidence": conf,
                "explanation": f"{sformat.replace('_', ' ').title()} via {partner} — ${value}/{'mo' if rev_model == 'recurring' else 'deal'} at {conf:.0%} confidence",
            })

    return sorted(results, key=lambda r: r["expected_value"] * r["confidence"], reverse=True)


# ── Phase B: Data Products ─────────────────────────────────────────────


def score_data_product_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    content_count = brand_ctx.get("content_count", 0)
    niche = brand_ctx.get("niche", "general")
    audience_size = brand_ctx.get("audience_size", 0)
    brand_ctx.get("offer_count", 0)
    avg_payout = brand_ctx.get("avg_payout", 1000)

    base_confidence = min(0.7, 0.15 + (content_count / 50) * 0.15 + (audience_size / 20000) * 0.15)

    product_configs = [
        ("niche_database", "researchers_and_analysts", "recurring", 97, 0.6,
         ["Identify niche data gaps", "Build collection pipeline", "Structure database", "Launch access portal", "Update regularly"]),
        ("premium_intelligence_feed", "decision_makers", "recurring", 197, 0.5,
         ["Define intelligence scope", "Build curation process", "Create delivery format", "Launch subscription", "Deliver weekly"]),
        ("swipe_file", "marketers_and_creators", "one_time", 47, 0.85,
         ["Curate winning examples", "Organize by category", "Design presentation", "Create checkout", "Deliver"]),
        ("research_pack", "strategists", "one_time", 297, 0.55,
         ["Define research scope", "Conduct analysis", "Package findings", "Create sales page", "Deliver"]),
        ("signal_trend_dataset", "investors_and_operators", "recurring", 497, 0.4,
         ["Identify signal sources", "Build data pipeline", "Validate accuracy", "Create API or feed", "Monetize access"]),
        ("premium_reporting_product", "executives_and_teams", "recurring", 297, 0.45,
         ["Define reporting scope", "Build data templates", "Automate collection", "Design reports", "Launch subscription"]),
    ]

    for ptype, segment, rev_model, price, conf_mult, steps in product_configs:
        conf = round(min(0.8, base_confidence * conf_mult), 3)

        if niche in ("tech", "finance", "saas", "marketing", "business"):
            conf = min(0.8, conf + 0.08)
            price = int(price * 1.3)

        if ptype in ("signal_trend_dataset", "premium_intelligence_feed") and content_count < 30:
            conf *= 0.4

        monthly = price if rev_model == "recurring" else 0
        annual_est = monthly * 12 if rev_model == "recurring" else price

        if conf >= 0.1:
            results.append({
                "product_type": ptype,
                "target_segment": segment,
                "revenue_model": rev_model,
                "price_band": "high" if annual_est > avg_payout else "mid" if annual_est > avg_payout * 0.3 else "low",
                "expected_value": round(float(annual_est), 2),
                "execution_plan": steps,
                "confidence": conf,
                "explanation": f"{ptype.replace('_', ' ').title()} for {segment} — ${price}/{'mo' if rev_model == 'recurring' else 'one-time'} at {conf:.0%} confidence",
            })

    return sorted(results, key=lambda r: r["expected_value"] * r["confidence"], reverse=True)


# ── Phase B Blocker Detection ──────────────────────────────────────────


def detect_phase_b_blockers(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    if brand_ctx.get("content_count", 0) < 15:
        blockers.append({
            "avenue_type": "licensing",
            "blocker_type": "insufficient_licensable_content",
            "severity": "high",
            "description": "Fewer than 15 content items. Licensing requires a substantial asset library.",
            "operator_action_needed": "Build content library to at least 15 items before licensing.",
        })
    if brand_ctx.get("content_count", 0) < 10:
        blockers.append({
            "avenue_type": "syndication",
            "blocker_type": "insufficient_syndication_content",
            "severity": "high",
            "description": "Fewer than 10 content items. Syndication partners require a content backlog.",
            "operator_action_needed": "Produce at least 10 content items for syndication deals.",
        })
    if brand_ctx.get("content_count", 0) < 20:
        blockers.append({
            "avenue_type": "data_products",
            "blocker_type": "insufficient_data_depth",
            "severity": "medium",
            "description": "Fewer than 20 content items. Data products need deep niche expertise proof.",
            "operator_action_needed": "Build content depth to at least 20 items before launching data products.",
        })
    if not brand_ctx.get("has_payment_processor"):
        blockers.append({
            "avenue_type": "all",
            "blocker_type": "no_payment_processor",
            "severity": "critical",
            "description": "No payment processor connected. Cannot sell licenses, syndication, or data products.",
            "operator_action_needed": "Connect Stripe, PayPal, or another payment processor.",
        })
    return blockers


# ── Phase C: Merch / Physical Products ─────────────────────────────────


def score_merch_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    audience_size = brand_ctx.get("audience_size", 0)
    niche = brand_ctx.get("niche", "general")
    content_count = brand_ctx.get("content_count", 0)
    has_avatar = brand_ctx.get("has_avatar", False)
    brand_ctx.get("offer_count", 0)

    base_confidence = min(0.7, 0.1 + (audience_size / 20000) * 0.2 + (content_count / 30) * 0.15)

    merch_configs = [
        ("creator_branded_drop", "loyal_followers", "mid", 3000, 0.7,
         ["Design drop concept", "Source production partner", "Create mockups", "Pre-sell campaign", "Fulfill orders"],
         "recommended"),
        ("evergreen_store_product", "general_audience", "low", 1200, 0.8,
         ["Select product type", "Design artwork", "Set up print-on-demand", "Create store page", "Launch + promote"],
         "recommended"),
        ("product_line_experiment", "early_adopters", "mid", 5000, 0.5,
         ["Identify niche product gap", "Prototype", "Small-batch production", "Beta launch", "Evaluate + iterate"],
         "recommended"),
        ("physical_bundle", "high_value_fans", "high", 8000, 0.4,
         ["Design premium bundle", "Source components", "Package design", "Limited pre-sale", "Ship + follow up"],
         "recommended"),
        ("limited_edition_release", "collectors_and_superfans", "high", 6000, 0.45,
         ["Define limited concept", "Set quantity cap", "Production run", "Exclusive launch window", "Fulfill + certify"],
         "recommended"),
    ]

    for pclass, segment, pband, value, conf_mult, steps, truth in merch_configs:
        conf = round(min(0.8, base_confidence * conf_mult), 3)

        if has_avatar:
            conf = min(0.8, conf + 0.05)
        if niche in ("lifestyle", "fitness", "fashion", "food", "gaming"):
            conf = min(0.8, conf + 0.08)
            value = int(value * 1.2)

        if audience_size < 2000 and pclass in ("physical_bundle", "limited_edition_release"):
            conf *= 0.3
        if not brand_ctx.get("has_payment_processor"):
            truth = "blocked"

        if conf >= 0.08:
            results.append({
                "product_class": pclass,
                "target_segment": segment,
                "price_band": pband,
                "expected_value": round(float(value), 2),
                "execution_plan": steps,
                "truth_label": truth,
                "confidence": conf,
                "explanation": f"{pclass.replace('_', ' ').title()} for {segment} — est. ${value:.0f} at {conf:.0%} confidence",
            })

    return sorted(results, key=lambda r: r["expected_value"] * r["confidence"], reverse=True)


# ── Phase C: Live Events ───────────────────────────────────────────────


def score_live_event_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    audience_size = brand_ctx.get("audience_size", 0)
    niche = brand_ctx.get("niche", "general")
    content_count = brand_ctx.get("content_count", 0)
    brand_ctx.get("has_avatar", False)
    brand_ctx.get("offer_count", 0)

    base_confidence = min(0.75, 0.15 + (content_count / 30) * 0.2 + (audience_size / 15000) * 0.15)

    event_configs = [
        ("webinar", "interested_audience", "free_with_upsell", "low", 500, 0.85,
         ["Pick topic from top content", "Create registration page", "Promote to list/audience", "Deliver live", "Follow-up with offer"],
         "recommended"),
        ("workshop", "skill_seekers", "paid", "mid", 2000, 0.65,
         ["Design curriculum", "Create landing page", "Price and promote", "Deliver workshop", "Collect feedback + upsell"],
         "recommended"),
        ("live_creator_session", "fans_and_followers", "paid", "low", 300, 0.8,
         ["Schedule session", "Promote on socials", "Go live", "Engage audience", "Replay access offer"],
         "recommended"),
        ("paid_live_event", "premium_audience", "paid", "high", 5000, 0.45,
         ["Design premium event", "Secure speakers/guests", "Build event page", "Sell tickets", "Deliver + record"],
         "recommended"),
        ("premium_qa_office_hours", "committed_learners", "paid", "mid", 1500, 0.7,
         ["Define topic scope", "Set recurring schedule", "Create booking page", "Deliver sessions", "Build community"],
         "recommended"),
        ("niche_event_product", "niche_professionals", "paid", "high", 8000, 0.35,
         ["Identify niche event gap", "Design unique format", "Secure venue/platform", "Market to niche", "Deliver + iterate"],
         "recommended"),
    ]

    for etype, segment, ticket, pband, value, conf_mult, steps, truth in event_configs:
        conf = round(min(0.85, base_confidence * conf_mult), 3)

        if niche in ("tech", "business", "finance", "marketing", "saas"):
            conf = min(0.85, conf + 0.05)
            value = int(value * 1.15)

        if etype == "niche_event_product" and audience_size < max(audience_size * 0.1, 1):
            conf *= 0.4
        if etype == "paid_live_event" and content_count < 15:
            conf *= 0.5

        if not brand_ctx.get("has_payment_processor") and ticket == "paid":
            truth = "blocked"

        if conf >= 0.08:
            results.append({
                "event_type": etype,
                "audience_segment": segment,
                "ticket_model": ticket,
                "price_band": pband,
                "expected_value": round(float(value), 2),
                "execution_plan": steps,
                "truth_label": truth,
                "confidence": conf,
                "explanation": f"{etype.replace('_', ' ').title()} for {segment} ({ticket}) — est. ${value:.0f} at {conf:.0%} confidence",
            })

    return sorted(results, key=lambda r: r["expected_value"] * r["confidence"], reverse=True)


# ── Phase C: Owned Affiliate Program ──────────────────────────────────


def score_owned_affiliate_opportunities(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    audience_size = brand_ctx.get("audience_size", 0)
    niche = brand_ctx.get("niche", "general")
    offer_count = brand_ctx.get("offer_count", 0)
    brand_ctx.get("content_count", 0)

    base_confidence = min(0.7, 0.1 + (offer_count / 5) * 0.25 + (audience_size / 20000) * 0.15)

    program_configs = [
        ("affiliate_recruitment", "micro_influencers", "percentage", "standard", 3000, 0.7,
         ["Define ideal affiliate profile", "Create recruitment page", "Outreach to prospects", "Onboard affiliates", "Track performance"],
         "recommended"),
        ("affiliate_program_launch", "content_creators", "percentage", "standard", 5000, 0.55,
         ["Choose affiliate platform", "Set commission structure", "Create affiliate portal", "Build marketing materials", "Launch program"],
         "recommended"),
        ("incentive_model_optimization", "existing_affiliates", "tiered_percentage", "gold", 2000, 0.6,
         ["Analyze current performance", "Design tier structure", "Model incentive economics", "Communicate changes", "Monitor uplift"],
         "queued"),
        ("partner_tier_expansion", "top_performers", "tiered_percentage", "platinum", 8000, 0.4,
         ["Identify top affiliates", "Design VIP tier", "Negotiate custom terms", "Onboard to tier", "Co-marketing initiatives"],
         "recommended"),
        ("affiliate_attribution_setup", "all_affiliates", "percentage", "standard", 1000, 0.75,
         ["Select tracking tool", "Implement tracking pixels", "Set attribution windows", "Test end-to-end", "Go live"],
         "queued"),
    ]

    for ptype, partner, incentive, tier, value, conf_mult, steps, truth in program_configs:
        conf = round(min(0.8, base_confidence * conf_mult), 3)

        if niche in ("tech", "saas", "business", "marketing", "finance"):
            conf = min(0.8, conf + 0.05)

        if offer_count == 0:
            conf *= 0.2
            truth = "blocked"
        if ptype == "partner_tier_expansion" and audience_size < max(audience_size * 0.1, 1):
            conf *= 0.3

        annual_est = value * 12 if incentive.startswith("tiered") else value

        if conf >= 0.05:
            results.append({
                "program_type": ptype,
                "target_partner_type": partner,
                "incentive_model": incentive,
                "partner_tier": tier,
                "expected_value": round(float(annual_est), 2),
                "execution_plan": steps,
                "truth_label": truth,
                "confidence": conf,
                "explanation": f"{ptype.replace('_', ' ').title()} targeting {partner} ({tier}) — est. ${annual_est:.0f} at {conf:.0%} confidence",
            })

    return sorted(results, key=lambda r: r["expected_value"] * r["confidence"], reverse=True)


# ── Phase C Blocker Detection ──────────────────────────────────────────


def detect_phase_c_blockers(brand_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    if brand_ctx.get("audience_size", 0) < 2000:
        blockers.append({
            "avenue_type": "merch",
            "blocker_type": "audience_too_small_for_merch",
            "severity": "high",
            "description": "Audience under 2,000. Merch drops need a minimum buying audience.",
            "operator_action_needed": "Grow audience to 2,000+ before launching merch.",
        })
    if brand_ctx.get("content_count", 0) < 10:
        blockers.append({
            "avenue_type": "live_events",
            "blocker_type": "insufficient_content_for_events",
            "severity": "medium",
            "description": "Fewer than 10 content items. Live events need proven topic authority.",
            "operator_action_needed": "Produce at least 10 content items to establish topic authority.",
        })
    if brand_ctx.get("offer_count", 0) == 0:
        blockers.append({
            "avenue_type": "owned_affiliate_program",
            "blocker_type": "no_offers_for_affiliate_program",
            "severity": "critical",
            "description": "No offers defined. An affiliate program requires at least one offer to promote.",
            "operator_action_needed": "Create at least one offer before launching an affiliate program.",
        })
    if not brand_ctx.get("has_payment_processor"):
        blockers.append({
            "avenue_type": "all",
            "blocker_type": "no_payment_processor",
            "severity": "critical",
            "description": "No payment processor. Cannot collect merch, event, or affiliate revenue.",
            "operator_action_needed": "Connect Stripe, PayPal, or another payment processor.",
        })
    return blockers


# ── Phase D: Unified Hub Engine ────────────────────────────────────────

AVENUE_DISPLAY_NAMES: dict[str, str] = {
    "ugc_services": "UGC / Creative Services",
    "consulting": "Services / Consulting",
    "premium_access": "Premium Access / Concierge",
    "licensing": "Licensing",
    "syndication": "Syndication",
    "data_products": "Data Products",
    "merch": "Merch / Physical Products",
    "live_events": "Live Events",
    "owned_affiliate_program": "Owned Affiliate Program",
}

AVENUE_MISSING_INTEGRATIONS: dict[str, list[str]] = {
    "ugc_services": [],
    "consulting": [],
    "premium_access": ["community_platform"],
    "licensing": ["payment_processor"],
    "syndication": ["payment_processor"],
    "data_products": ["payment_processor"],
    "merch": ["payment_processor", "fulfillment_provider"],
    "live_events": ["payment_processor", "event_platform"],
    "owned_affiliate_program": ["affiliate_tracking_tool"],
}


def classify_avenue_truth_state(
    action_count: int,
    blocked_count: int,
    blocker_count: int,
    has_revenue: bool,
) -> str:
    if has_revenue:
        return "live"
    if action_count == 0:
        return "recommended"
    if blocked_count > 0 and blocked_count == action_count:
        return "blocked"
    if blocker_count > 0 and action_count > blocked_count:
        return "queued"
    if action_count > 0 and blocker_count == 0:
        return "executing"
    return "recommended"


def determine_operator_next_action(
    avenue_type: str,
    truth_state: str,
    blocker_types: list[str],
) -> str:
    if truth_state == "live":
        return "Monitor performance and optimize."
    if truth_state == "blocked":
        if "no_payment_processor" in blocker_types:
            return "Connect a payment processor to unblock revenue collection."
        if "insufficient_portfolio" in blocker_types:
            return "Build portfolio content to establish credibility."
        if "no_offers_defined" in blocker_types or "no_offers_for_affiliate_program" in blocker_types:
            return "Create at least one offer in the Offer Catalog."
        if "audience_too_small" in blocker_types or "audience_too_small_for_merch" in blocker_types:
            return "Grow audience before launching this avenue."
        return f"Resolve blockers for {AVENUE_DISPLAY_NAMES.get(avenue_type, avenue_type)}."
    if truth_state == "queued":
        return f"Review queued plans for {AVENUE_DISPLAY_NAMES.get(avenue_type, avenue_type)} and resolve remaining blockers."
    if truth_state == "executing":
        return f"Execute the planned actions for {AVENUE_DISPLAY_NAMES.get(avenue_type, avenue_type)}."
    return f"Recompute {AVENUE_DISPLAY_NAMES.get(avenue_type, avenue_type)} to generate plans."


def rank_hub_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank hub entries by composite score: value × confidence × urgency × readiness."""
    state_urgency = {"blocked": 0.3, "recommended": 0.5, "queued": 0.7, "executing": 0.9, "live": 1.0}
    state_readiness = {"blocked": 0.1, "recommended": 0.4, "queued": 0.6, "executing": 0.9, "live": 1.0}

    for e in entries:
        urgency = state_urgency.get(e["truth_state"], 0.5)
        readiness = state_readiness.get(e["truth_state"], 0.4)
        value = e.get("total_expected_value", 0)
        conf = e.get("avg_confidence", 0)
        e["hub_score"] = round(value * conf * urgency * readiness / 1000, 3)

    return sorted(entries, key=lambda e: e["hub_score"], reverse=True)


def build_event_rollup(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate revenue events into per-avenue and total rollups."""
    by_avenue: dict[str, dict[str, float]] = {}
    total_revenue = 0.0
    total_cost = 0.0
    total_profit = 0.0
    event_count = len(events)

    for ev in events:
        at = ev.get("avenue_type", "unknown")
        r, c, p = ev.get("revenue", 0), ev.get("cost", 0), ev.get("profit", 0)
        total_revenue += r
        total_cost += c
        total_profit += p
        if at not in by_avenue:
            by_avenue[at] = {"revenue": 0, "cost": 0, "profit": 0, "count": 0}
        by_avenue[at]["revenue"] += r
        by_avenue[at]["cost"] += c
        by_avenue[at]["profit"] += p
        by_avenue[at]["count"] += 1

    return {
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_profit, 2),
        "event_count": event_count,
        "by_avenue": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_avenue.items()},
    }
