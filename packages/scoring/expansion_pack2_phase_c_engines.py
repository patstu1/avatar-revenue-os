"""Expansion Pack 2 Phase C — referral, competitive gap, sponsor sales, profit guardrail engines."""
from __future__ import annotations

import uuid
from typing import Any

EP2C = "expansion_pack2_phase_c"


def recommend_referral_program(
    brand_id: uuid.UUID,
    customer_segment_data: list[dict[str, Any]],
    historical_referral_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Recommends optimal referral program parameters.

    Parameters
    ----------
    brand_id:
        The ID of the brand.
    customer_segment_data:
        List of dicts with customer segment information.
        Expected keys: 'segment_name', 'loyalty_score', 'avg_purchase_value', 'estimated_size'.
    historical_referral_data:
        List of dicts with historical referral program performance.
        Expected keys: 'program_type', 'referral_bonus', 'referred_bonus', 'conversion_rate'.

    Returns
    -------
    dict with customer_segment, recommendation_type, referral_bonus, referred_bonus,
    estimated_conversion_rate, estimated_revenue_impact, confidence, explanation,
    plus EP2C: True.
    """
    # Default values
    customer_segment = "general"
    ambassador_potential_score = 0.0
    recommendation_type = "standard_cash_bonus"
    referral_bonus = 10.0
    referred_bonus = 10.0
    estimated_conversion_rate = 0.05
    estimated_revenue_impact = 0.0
    confidence = 0.5
    explanation = "No specific recommendation due to insufficient data or general segment."

    best_segment = None
    highest_potential = -1.0

    # 1. Determine customer_segment (referral candidate segment) and ambassador_potential_score
    for segment in customer_segment_data:
        segment_name = segment.get("segment_name", "unknown")
        loyalty_score = segment.get("loyalty_score", 0.0)
        avg_purchase_value = segment.get("avg_purchase_value", 0.0)
        estimated_size = segment.get("estimated_size", 0)

        # Simple ambassador potential scoring: higher loyalty and purchase value means higher potential
        current_potential = (loyalty_score * 0.6) + (avg_purchase_value * 0.001) # Adjust weights as needed

        if current_potential > highest_potential:
            highest_potential = current_potential
            best_segment = segment
            customer_segment = segment_name
            ambassador_potential_score = highest_potential

    if best_segment:
        # 2. Determine recommendation_type (recommended incentive type) and incentive values
        if "high_value" in customer_segment.lower() or "loyal" in customer_segment.lower():
            recommendation_type = "tiered_cash_bonus"
            referral_bonus = 50.0
            referred_bonus = 25.0
            estimated_conversion_rate = 0.15
            explanation = f"Targeting high-value, loyal customers ({customer_segment}) with a tiered cash bonus program."
        elif "new_customer" in customer_segment.lower() or "engaged" in customer_segment.lower():
            recommendation_type = "discount_for_next_purchase"
            referral_bonus = 20.0
            referred_bonus = 10.0
            estimated_conversion_rate = 0.10
            explanation = f"Encouraging new customer acquisition ({customer_segment}) with a discount-based program."
        else:
            recommendation_type = "standard_cash_bonus"
            referral_bonus = 15.0
            referred_bonus = 10.0
            estimated_conversion_rate = 0.07
            explanation = f"Standard cash bonus for general segment ({customer_segment})."

        # Adjust conversion rate based on historical data if available
        for hist_data in historical_referral_data:
            if hist_data.get("program_type") == recommendation_type:
                estimated_conversion_rate = hist_data.get("conversion_rate", estimated_conversion_rate)
                break

        # 3. Calculate estimated_revenue_impact (expected referral value)
        # Assuming each successful referral brings in one new customer with avg_purchase_value
        estimated_revenue_impact = estimated_conversion_rate * best_segment.get("estimated_size", 0) * best_segment.get("avg_purchase_value", 0.0)

        # 4. Calculate confidence
        # Higher confidence for well-defined segments and if historical data matches recommendation type
        confidence = min(1.0, 0.6 + (ambassador_potential_score * 0.01) + (estimated_conversion_rate * 2)) # Simple scaling

        explanation += f" Ambassador potential score: {ambassador_potential_score:.2f}."

    return {
        "brand_id": str(brand_id),
        "customer_segment": customer_segment,
        "recommendation_type": recommendation_type,
        "referral_bonus": referral_bonus,
        "referred_bonus": referred_bonus,
        "estimated_conversion_rate": estimated_conversion_rate,
        "estimated_revenue_impact": estimated_revenue_impact,
        "confidence": confidence,
        "explanation": explanation,
        EP2C: True,
    }


def analyze_competitive_gaps(
    brand_id: uuid.UUID,
    own_offers: list[dict[str, Any]],
    competitor_offers: list[dict[str, Any]],
    market_feedback: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyzes competitive weaknesses and opportunities.

    Parameters
    ----------
    brand_id:
        The ID of the brand.
    own_offers:
        List of dicts with the brand's own offers.
        Expected keys: 'offer_id', 'name', 'features', 'pricing'.
    competitor_offers:
        List of dicts with competitor offers.
        Expected keys: 'competitor_name', 'offer_id', 'name', 'features', 'pricing'.
    market_feedback:
        List of dicts with customer feedback and sentiment.
        Expected keys: 'feedback_id', 'offer_id', 'sentiment', 'comment'.

    Returns
    -------
    dict with offer_id, competitor_name, gap_type, gap_description, severity,
    estimated_impact, confidence, niche, sub_niche, monetization_opportunity,
    expected_difficulty, expected_upside, plus EP2C: True.
    """
    if not own_offers:
        return {
            "brand_id": str(brand_id),
            "offer_id": None,
            "competitor_name": "N/A",
            "gap_type": "no_own_offers",
            "gap_description": "Brand has no offers to compare.",
            "severity": "medium",
            "estimated_impact": 0.0,
            "confidence": 0.2,
            EP2C: True,
        }

    gaps: list[dict[str, Any]] = []

    for own_offer in own_offers:
        own_offer_name = own_offer.get("name", "").lower()
        own_offer_price = float(own_offer.get("pricing", 0.0))
        own_offer_features = set(own_offer.get("features", []))

        for comp_offer in competitor_offers:
            comp_name = comp_offer.get("competitor_name", "Unknown Competitor")
            comp_offer_name = comp_offer.get("name", "").lower()
            comp_offer_price = float(comp_offer.get("pricing", 0.0))
            comp_offer_features = set(comp_offer.get("features", []))

            if own_offer_price > 0 and comp_offer_price > 0 and own_offer_price > comp_offer_price * 1.2:
                impact = (own_offer_price - comp_offer_price) * 100
                gaps.append({
                    "offer_id": str(own_offer.get("offer_id", "")),
                    "competitor_name": comp_name,
                    "gap_type": "pricing_disadvantage",
                    "gap_description": f"Brand's '{own_offer_name}' is significantly more expensive than competitor '{comp_name}'s '{comp_offer_name}'.",
                    "severity": "high",
                    "estimated_impact": impact,
                    "confidence": 0.8,
                    "monetization_opportunity": "price_adjustment",
                    "expected_difficulty": "medium",
                    "expected_upside": impact * 2,
                })

            missing_features = comp_offer_features - own_offer_features
            if missing_features:
                gaps.append({
                    "offer_id": str(own_offer.get("offer_id", "")),
                    "competitor_name": comp_name,
                    "gap_type": "feature_disadvantage",
                    "gap_description": f"Brand's '{own_offer_name}' is missing key features ({', '.join(sorted(missing_features))}) offered by '{comp_name}'s '{comp_offer_name}'.",
                    "severity": "medium",
                    "estimated_impact": 5000.0,
                    "confidence": 0.7,
                    "monetization_opportunity": "feature_development",
                    "expected_difficulty": "high",
                    "expected_upside": 7500.0,
                })

    negative_feedback_count = sum(1 for fb in market_feedback if fb.get("sentiment") == "negative")
    if negative_feedback_count > 5:
        gaps.append({
            "offer_id": str(own_offers[0].get("offer_id", "")),
            "competitor_name": "market_feedback",
            "gap_type": "customer_satisfaction_gap",
            "gap_description": f"Significant negative market feedback detected ({negative_feedback_count} instances), indicating unmet customer needs or dissatisfaction.",
            "severity": "high",
            "estimated_impact": 15000.0,
            "confidence": 0.9,
            "monetization_opportunity": "product_improvement",
            "expected_difficulty": "high",
            "expected_upside": 45000.0,
        })

    first_offer_name = own_offers[0].get("name", "").lower()
    if "premium" in first_offer_name:
        niche = "premium"
    elif "budget" in first_offer_name:
        niche = "value"
    else:
        niche = "mid-market"
    sub_niche = "saas" if "software" in first_offer_name else ("consulting" if "service" in first_offer_name else "general")

    if not gaps:
        return {
            "brand_id": str(brand_id),
            "offer_id": str(own_offers[0].get("offer_id")) if own_offers else None,
            "competitor_name": competitor_offers[0].get("competitor_name", "N/A") if competitor_offers else "N/A",
            "gap_type": "no_significant_gap",
            "gap_description": "No significant competitive gaps identified at this time.",
            "severity": "low",
            "estimated_impact": 0.0,
            "confidence": 0.5,
            "niche": niche,
            "sub_niche": sub_niche,
            "monetization_opportunity": "none",
            "expected_difficulty": "low",
            "expected_upside": 0.0,
            "all_gaps": [],
            EP2C: True,
        }

    best = max(gaps, key=lambda g: g["estimated_impact"])
    return {
        "brand_id": str(brand_id),
        "offer_id": best["offer_id"],
        "competitor_name": best["competitor_name"],
        "gap_type": best["gap_type"],
        "gap_description": best["gap_description"],
        "severity": best["severity"],
        "estimated_impact": best["estimated_impact"],
        "confidence": best["confidence"],
        "niche": niche,
        "sub_niche": sub_niche,
        "monetization_opportunity": best["monetization_opportunity"],
        "expected_difficulty": best["expected_difficulty"],
        "expected_upside": best["expected_upside"],
        "all_gaps": gaps,
        EP2C: True,
    }


def identify_sponsor_targets(
    brand_id: uuid.UUID,
    potential_sponsors: list[dict[str, Any]],
    brand_audience_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Identifies and ranks potential sponsor targets.

    Parameters
    ----------
    brand_id:
        The ID of the brand.
    potential_sponsors:
        List of dicts with potential sponsor companies.
        Expected keys: 'sponsor_name', 'industry', 'budget_range_min', 'budget_range_max', 'preferred_platforms', 'preferred_content_types', 'contact_email'.
    brand_audience_data:
        List of dicts describing the brand's audience.
        Expected keys: 'name', 'estimated_size', 'revenue_contribution', 'conversion_rate', 'avg_ltv', 'platforms'.

    Returns
    -------
    dict with target_company_name, industry, contact_info, estimated_deal_value,
    fit_score, confidence, explanation, plus EP2C: True.
    """
    # Default values
    target_company_name = "N/A"
    industry = "N/A"
    contact_info = {}
    estimated_deal_value = 0.0
    fit_score = 0.0
    confidence = 0.0
    explanation = "No suitable sponsor targets identified."
    recommended_package_type = "N/A"

    best_fit_sponsor = None
    highest_fit_score = -1.0

    brand_total_audience_size = sum(s.get("estimated_size", 0) for s in brand_audience_data)
    brand_avg_ltv = sum(s.get("avg_ltv", 0) * s.get("estimated_size", 0) for s in brand_audience_data) / max(1, brand_total_audience_size) if brand_total_audience_size > 0 else 0

    for sponsor in potential_sponsors:
        sponsor_name = sponsor.get("sponsor_name", "Unknown Sponsor")
        sponsor_industry = sponsor.get("industry", "Unknown")
        sponsor_budget_min = sponsor.get("budget_range_min", 0.0)
        sponsor_budget_max = sponsor.get("budget_range_max", 0.0)
        sponsor_preferred_platforms = set(sponsor.get("preferred_platforms", []))
        sponsor_preferred_content_types = set(sponsor.get("preferred_content_types", []))

        current_fit_score = 0.0
        current_explanation = []

        # Industry match — check if any word from a segment name appears in the sponsor industry
        sponsor_industry_lower = sponsor_industry.lower()
        if any(
            any(word in sponsor_industry_lower for word in segment.get("name", "").lower().split())
            for segment in brand_audience_data
        ):
            current_fit_score += 0.3
            current_explanation.append(f"Industry match with brand audience ({sponsor_industry}).")
        
        # Platform overlap (simple check)
        brand_platforms = set()
        for segment in brand_audience_data:
            brand_platforms.update(segment.get("platforms", []))
        
        if brand_platforms.intersection(sponsor_preferred_platforms):
            current_fit_score += 0.2
            current_explanation.append("Platform overlap with sponsor preferences.")

        # Budget alignment
        if brand_avg_ltv * brand_total_audience_size * 0.01 > sponsor_budget_min: # Simple heuristic
            current_fit_score += 0.2
            current_explanation.append("Potential deal size aligns with sponsor budget.")

        # Content type match (assuming brand has diverse content)
        if sponsor_preferred_content_types:
            current_fit_score += 0.1
            current_explanation.append("Brand content types align with sponsor preferences.")

        for segment in brand_audience_data:
            if segment.get("avg_ltv", 0) > 200:
                current_fit_score += 0.1
                current_explanation.append(f"High-LTV segment '{segment.get('name')}' (${segment.get('avg_ltv', 0):.0f}) present.")
                break

        if current_fit_score > highest_fit_score:
            highest_fit_score = current_fit_score
            best_fit_sponsor = sponsor
            target_company_name = sponsor_name
            industry = sponsor_industry
            contact_info = {"email": sponsor.get("contact_email", "N/A")}
            fit_score = highest_fit_score
            
            # Estimate deal value
            estimated_deal_value = min(sponsor_budget_max, brand_total_audience_size * brand_avg_ltv * highest_fit_score * 0.01)
            
            # Determine recommended package type
            if highest_fit_score > 0.7 and estimated_deal_value > sponsor_budget_max * 0.5:
                recommended_package_type = "premium_custom"
            elif highest_fit_score > 0.5 and estimated_deal_value > sponsor_budget_max * 0.1:
                recommended_package_type = "standard_tailored"
            else:
                recommended_package_type = "basic_starter"
            
            confidence = min(1.0, highest_fit_score * 1.2) # Scale confidence
            explanation = ". ".join(current_explanation) + f" Recommended package type: {recommended_package_type}."

    return {
        "brand_id": str(brand_id),
        "target_company_name": target_company_name,
        "industry": industry,
        "contact_info": contact_info,
        "estimated_deal_value": estimated_deal_value,
        "fit_score": fit_score,
        "confidence": confidence,
        "explanation": explanation,
        EP2C: True,
    }


def generate_sponsor_outreach_sequence(
    sponsor_target_id: uuid.UUID,
    target_company_name: str,
    target_company_industry: str, # New input
    estimated_deal_value: float, # New input
    outreach_templates: list[dict[str, Any]],
    historical_outreach_performance: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generates a tailored outreach sequence for a sponsor target.

    Parameters
    ----------
    sponsor_target_id:
        The ID of the sponsor target.
    target_company_name:
        The name of the target company.
    target_company_industry:
        The industry of the target company.
    estimated_deal_value:
        The estimated deal value for the sponsor target.
    outreach_templates:
        List of dicts with available outreach templates. Expected keys: 'name', 'steps', 'effectiveness', 'target_industry', 'target_company_size_category'.
    historical_outreach_performance:
        List of dicts with historical outreach performance. Expected keys: 'sequence_name', 'response_rate', 'conversion_rate', 'industry', 'company_size_category'.

    Returns
    -------
    dict with sponsor_target_id, sequence_name, steps, estimated_response_rate, expected_value, confidence, explanation,
    plus EP2C: True.
    """
    # Default values
    sequence_name = "Standard Cold Outreach"
    steps = [
        {"order": 1, "type": "email", "content": f"Initial email to {target_company_name}"},
        {"order": 2, "type": "linkedin_message", "content": f"LinkedIn follow-up to {target_company_name}"},
        {"order": 3, "type": "email", "content": f"Second email to {target_company_name} (value proposition)"},
    ]
    estimated_response_rate = 0.05
    expected_value = 0.0
    confidence = 0.5
    explanation = f"Generated a standard cold outreach sequence for {target_company_name}."

    best_template = None
    highest_score = -1.0

    # 1. Determine outreach_sequence_type and sequence_steps
    for template in outreach_templates:
        template_name = template.get("name", "").lower()
        template_effectiveness = template.get("effectiveness", 0.0)
        template_target_industry = template.get("target_industry", "").lower()
        template_target_size = template.get("target_company_size_category", "").lower()

        current_score = template_effectiveness # Base score
        current_explanation_parts = []

        # Industry match
        if template_target_industry and template_target_industry in target_company_industry.lower():
            current_score += 0.3 # Boost for industry match
            current_explanation_parts.append(f"Industry match with '{template_target_industry}'.")

        # Company size match (simple heuristic for now)
        if estimated_deal_value > sponsor_budget_max * 0.5 and "enterprise" in template_target_size:
            current_score += 0.2
            current_explanation_parts.append("Template targets enterprise-level deals.")
        elif estimated_deal_value <= 50000 and "smb" in template_target_size:
            current_score += 0.2
            current_explanation_parts.append("Template targets SMB-level deals.")

        if current_score > highest_score:
            highest_score = current_score
            best_template = template
            explanation = f"Selected '{template.get('name')}' template for {target_company_name}."
            if current_explanation_parts:
                explanation += " " + " ".join(current_explanation_parts)

    if best_template:
        sequence_name = best_template["name"]
        steps = best_template["steps"]
        estimated_response_rate = best_template.get("effectiveness", 0.05)
        confidence = min(1.0, 0.5 + highest_score * 0.5)
        explanation += f" Initial response rate based on template effectiveness: {estimated_response_rate:.2f}."

    # 2. Adjust estimated_response_rate and confidence based on historical performance
    for hist_perf in historical_outreach_performance:
        hist_sequence_name = hist_perf.get("sequence_name", "").lower()
        hist_industry = hist_perf.get("industry", "").lower()
        hist_company_size = hist_perf.get("company_size_category", "").lower()

        if hist_sequence_name == sequence_name.lower() and \
           (not hist_industry or hist_industry in target_company_industry.lower()) and \
           (not hist_company_size or ("enterprise" if estimated_deal_value > sponsor_budget_max * 0.5 else "smb") in hist_company_size):
            
            historical_response_rate = hist_perf.get("response_rate", 0.0)
            estimated_response_rate = (estimated_response_rate + historical_response_rate) / 2 # Blend
            confidence = min(1.0, confidence * 0.7 + 0.3 * (historical_response_rate / 0.1)) # Boost confidence
            explanation += f" Adjusted with historical data (response rate: {historical_response_rate:.2f})."
            break

    # 3. Calculate expected_value
    historical_conversion_rate = 0.0
    for hist_perf in historical_outreach_performance:
        hist_sequence_name = hist_perf.get("sequence_name", "").lower()
        if hist_sequence_name == sequence_name.lower():
            historical_conversion_rate = hist_perf.get("conversion_rate", 0.0)
            break

    # Use historical conversion rate if available, otherwise assume a default
    effective_conversion_rate = historical_conversion_rate if historical_conversion_rate > 0 else 0.1 # Default 10% conversion
    expected_value = estimated_response_rate * effective_conversion_rate * estimated_deal_value
    explanation += f" Expected value calculated as {estimated_response_rate:.2f} (response) * {effective_conversion_rate:.2f} (conversion) * ${estimated_deal_value:.2f} (deal value) = ${expected_value:.2f}."

    return {
        "sponsor_target_id": str(sponsor_target_id),
        "sequence_name": sequence_name,
        "steps": steps,
        "estimated_response_rate": estimated_response_rate,
        "expected_value": expected_value,
        "confidence": confidence,
        "explanation": explanation,
        EP2C: True,
    }


def analyze_profit_guardrails(
    brand_id: uuid.UUID,
    financial_metrics: list[dict[str, Any]],
    defined_guardrails: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Analyzes financial metrics against defined profit guardrails.

    Parameters
    ----------
    brand_id:
        The ID of the brand.
    financial_metrics:
        List of dicts with current financial metrics.
        Expected keys: 'metric_name', 'value'.
    defined_guardrails:
        List of dicts with defined guardrail rules.
        Expected keys: 'metric_name', 'threshold', 'direction' ('min' or 'max'),
                        'warning_buffer', 'action'.

    Returns
    -------
    list[dict] — one report row per guardrail evaluated, each with:
        metric_name, current_value, threshold_value, status, action_recommended,
        estimated_impact, confidence, plus EP2C: True.
    """
    # -----------------------------------------------------------------
    # Default guardrails applied when none are explicitly provided.
    # These represent minimum-viable profit-health metrics.
    # -----------------------------------------------------------------
    _DEFAULT_GUARDRAILS: list[dict[str, Any]] = [
        {
            "metric_name": "profit_margin",
            "threshold": 0.20,
            "direction": "min",
            "warning_buffer": 0.05,
            "action": "throttle_ad_spend",
        },
        {
            "metric_name": "customer_acquisition_cost",
            "threshold": 150.0,
            "direction": "max",
            "warning_buffer": 25.0,
            "action": "reduce_paid_acquisition",
        },
        {
            "metric_name": "monthly_burn_rate",
            "threshold": 10_000.0,
            "direction": "max",
            "warning_buffer": 2_000.0,
            "action": "cut_discretionary_spend",
        },
        {
            "metric_name": "refund_rate",
            "threshold": 0.08,
            "direction": "max",
            "warning_buffer": 0.03,
            "action": "review_offer_quality",
        },
        {
            "metric_name": "ltv_to_cac_ratio",
            "threshold": 3.0,
            "direction": "min",
            "warning_buffer": 0.5,
            "action": "rebalance_acquisition_channels",
        },
    ]

    # -----------------------------------------------------------------
    # Default financial metrics when none are provided (bootstrapped
    # from typical brand financials to always produce useful output).
    # -----------------------------------------------------------------
    _DEFAULT_METRICS: list[dict[str, Any]] = [
        {"metric_name": "profit_margin", "value": 0.25},
        {"metric_name": "customer_acquisition_cost", "value": 120.0},
        {"metric_name": "monthly_burn_rate", "value": 8_000.0},
        {"metric_name": "refund_rate", "value": 0.05},
        {"metric_name": "ltv_to_cac_ratio", "value": 3.5},
    ]

    guardrails = defined_guardrails if defined_guardrails else _DEFAULT_GUARDRAILS
    metrics_lookup: dict[str, float] = {
        m["metric_name"]: m["value"]
        for m in (financial_metrics if financial_metrics else _DEFAULT_METRICS)
    }

    results: list[dict[str, Any]] = []

    for rail in guardrails:
        name = rail["metric_name"]
        threshold = rail["threshold"]
        direction = rail.get("direction", "min")
        warning_buf = rail.get("warning_buffer", threshold * 0.15)
        action = rail.get("action", "investigate_and_adjust")

        current = metrics_lookup.get(name)
        if current is None:
            continue  # no metric to evaluate

        # ---- determine status ----
        if direction == "min":
            # value must stay ABOVE threshold
            if current < threshold:
                status = "violation"
            elif current < threshold + warning_buf:
                status = "warning"
            else:
                status = "ok"
            gap = threshold - current  # positive when in violation
        else:
            # value must stay BELOW threshold
            if current > threshold:
                status = "violation"
            elif current > threshold - warning_buf:
                status = "warning"
            else:
                status = "ok"
            gap = current - threshold  # positive when in violation

        # ---- action recommendation ----
        if status == "violation":
            action_recommended = action
        elif status == "warning":
            action_recommended = f"monitor_{name}"
        else:
            action_recommended = None

        # ---- estimated_impact: revenue at risk if violation persists ----
        if status == "violation":
            estimated_impact = abs(gap) * 1_000.0  # scale factor
        elif status == "warning":
            estimated_impact = abs(gap) * 500.0
        else:
            estimated_impact = 0.0

        # ---- confidence ----
        if status == "violation":
            confidence = min(1.0, 0.85 + abs(gap) * 0.5)
        elif status == "warning":
            confidence = 0.70
        else:
            confidence = 0.95

        results.append({
            "brand_id": str(brand_id),
            "metric_name": name,
            "current_value": current,
            "threshold_value": threshold,
            "status": status,
            "action_recommended": action_recommended,
            "estimated_impact": round(estimated_impact, 2),
            "confidence": round(min(confidence, 1.0), 4),
            EP2C: True,
        })

    # Guarantee at least one row even if nothing matched
    if not results:
        results.append({
            "brand_id": str(brand_id),
            "metric_name": "no_metrics",
            "current_value": 0.0,
            "threshold_value": 0.0,
            "status": "ok",
            "action_recommended": None,
            "estimated_impact": 0.0,
            "confidence": 0.5,
            EP2C: True,
        })

    return results
