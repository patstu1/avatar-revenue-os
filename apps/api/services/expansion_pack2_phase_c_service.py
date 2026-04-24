"""Expansion Pack 2 Phase C — referral, competitive gap, sponsor sales, profit guardrail services."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand
from packages.db.models.expansion_pack2_phase_c import (
    CompetitiveGapReport,
    ProfitGuardrailReport,
    ReferralProgramRecommendation,
    SponsorOutreachSequence,
    SponsorTarget,
)
from packages.db.models.offers import AudienceSegment, Offer, SponsorProfile
from packages.scoring.expansion_pack2_phase_c_engines import (
    analyze_competitive_gaps,
    analyze_profit_guardrails,
    generate_sponsor_outreach_sequence,
    identify_sponsor_targets,
    recommend_referral_program,
)


async def recompute_referral_program_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Fetch real customer segment data
    audience_segments = list(
        (
            await db.execute(
                select(AudienceSegment).where(
                    AudienceSegment.brand_id == brand_id,
                    AudienceSegment.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    customer_segment_data = [
        {
            "segment_name": s.name,
            "loyalty_score": s.conversion_rate * 10,  # Proxy for loyalty score
            "avg_purchase_value": s.avg_ltv,
            "estimated_size": s.estimated_size,
        }
        for s in audience_segments
    ]

    # DATA BOUNDARY: Static referral benchmarks — no live referral tracking feed yet.
    # Engine uses these as priors; replace with real program data when available.
    historical_referral_data = [
        {'program_type': 'tiered_cash_bonus', 'referral_bonus': 50.0, 'referred_bonus': 25.0, 'conversion_rate': 0.15},
        {'program_type': 'discount_for_next_purchase', 'referral_bonus': 20.0, 'referred_bonus': 10.0, 'conversion_rate': 0.10},
        {'program_type': 'standard_cash_bonus', 'referral_bonus': 15.0, 'referred_bonus': 10.0, 'conversion_rate': 0.07},
    ]

    await db.execute(delete(ReferralProgramRecommendation).where(ReferralProgramRecommendation.brand_id == brand_id))

    recommendation = recommend_referral_program(
        brand_id=brand_id,
        customer_segment_data=customer_segment_data,
        historical_referral_data=historical_referral_data,
    )

    db.add(
        ReferralProgramRecommendation(
            brand_id=brand_id,
            customer_segment=recommendation["customer_segment"],
            recommendation_type=recommendation["recommendation_type"],
            referral_bonus=recommendation["referral_bonus"],
            referred_bonus=recommendation["referred_bonus"],
            estimated_conversion_rate=recommendation["estimated_conversion_rate"],
            estimated_revenue_impact=recommendation["estimated_revenue_impact"],
            confidence=recommendation["confidence"],
            explanation=recommendation["explanation"],
        )
    )
    await db.flush()
    return {"referral_recommendations_count": 1}


async def get_referral_program_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(ReferralProgramRecommendation)
            .where(ReferralProgramRecommendation.brand_id == brand_id, ReferralProgramRecommendation.is_active.is_(True))
            .order_by(ReferralProgramRecommendation.estimated_revenue_impact.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "customer_segment": r.customer_segment,
            "recommendation_type": r.recommendation_type,
            "referral_bonus": r.referral_bonus,
            "referred_bonus": r.referred_bonus,
            "estimated_conversion_rate": r.estimated_conversion_rate,
            "estimated_revenue_impact": r.estimated_revenue_impact,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def recompute_competitive_gap_reports(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Fetch real own offers
    offers = list(
        (
            await db.execute(
                select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    own_offers = [
        {
            "offer_id": str(o.id),
            "name": o.name,
            "features": o.audience_fit_tags, # Using audience_fit_tags as a proxy for features
            "pricing": o.payout_amount,
        }
        for o in offers
    ]

    # DATA BOUNDARY: Static competitor benchmarks — no live competitive intel feed yet.
    competitor_offers = [
        {'competitor_name': 'CompCo Basic', 'offer_id': 'comp_offer_1', 'name': 'Basic Product', 'features': ['A', 'B'], 'pricing': 90.0},
        {'competitor_name': 'CompCo Premium', 'offer_id': 'comp_offer_2', 'name': 'Premium Product', 'features': ['A', 'B', 'C', 'D'], 'pricing': 150.0},
    ]

    # DATA BOUNDARY: Static market feedback — no live sentiment feed yet.
    market_feedback = [
        {'feedback_id': 'fb_1', 'offer_id': own_offers[0]['offer_id'] if own_offers else None, 'sentiment': 'negative', 'comment': 'Missing feature X'},
        {'feedback_id': 'fb_2', 'offer_id': 'comp_offer_1', 'sentiment': 'positive', 'comment': 'Great value for money'},
        {'feedback_id': 'fb_3', 'offer_id': own_offers[0]['offer_id'] if own_offers else None, 'sentiment': 'negative', 'comment': 'Too expensive compared to alternatives'},
    ]

    await db.execute(delete(CompetitiveGapReport).where(CompetitiveGapReport.brand_id == brand_id))

    report = analyze_competitive_gaps(
        brand_id=brand_id,
        own_offers=own_offers,
        competitor_offers=competitor_offers,
        market_feedback=market_feedback,
    )

    # Combine new fields into gap_description for persistence
    full_gap_description = report["gap_description"]
    if report.get("niche"):
        full_gap_description += f" Niche: {report['niche']}."
    if report.get("sub_niche"):
        full_gap_description += f" Sub-niche: {report['sub_niche']}."
    if report.get("monetization_opportunity"):
        full_gap_description += f" Monetization Opportunity: {report['monetization_opportunity']}."
    if report.get("expected_difficulty"):
        full_gap_description += f" Expected Difficulty: {report['expected_difficulty']}."
    if report.get("expected_upside"):
        full_gap_description += f" Expected Upside: {report['expected_upside']:.2f}."

    db.add(
        CompetitiveGapReport(
            brand_id=brand_id,
            offer_id=uuid.UUID(report["offer_id"]) if report["offer_id"] else None,
            competitor_name=report["competitor_name"],
            gap_type=report["gap_type"],
            gap_description=full_gap_description,
            severity=report["severity"],
            estimated_impact=report["estimated_impact"],
            confidence=report["confidence"],
        )
    )
    await db.flush()
    return {"competitive_gap_reports_count": 1}


async def get_competitive_gap_reports(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(CompetitiveGapReport)
            .where(CompetitiveGapReport.brand_id == brand_id, CompetitiveGapReport.is_active.is_(True))
            .order_by(CompetitiveGapReport.estimated_impact.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "offer_id": str(r.offer_id) if r.offer_id else None,
            "competitor_name": r.competitor_name,
            "gap_type": r.gap_type,
            "gap_description": r.gap_description,
            "severity": r.severity,
            "estimated_impact": r.estimated_impact,
            "confidence": r.confidence,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def recompute_sponsor_targets(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Fetch real potential sponsors
    sponsor_profiles = list(
        (
            await db.execute(
                select(SponsorProfile).where(
                    SponsorProfile.brand_id == brand_id,
                    SponsorProfile.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    potential_sponsors = [
        {
            "sponsor_name": sp.sponsor_name,
            "industry": sp.industry,
            "budget_range_min": sp.budget_range_min,
            "budget_range_max": sp.budget_range_max,
            "preferred_platforms": sp.preferred_platforms,
            "preferred_content_types": sp.preferred_content_types,
            "contact_email": sp.contact_email,
        }
        for sp in sponsor_profiles
    ]

    # Fetch real brand audience data
    audience_segments = list(
        (
            await db.execute(
                select(AudienceSegment).where(
                    AudienceSegment.brand_id == brand_id,
                    AudienceSegment.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    brand_audience_data = [
        {
            "name": s.name,
            "estimated_size": s.estimated_size,
            "revenue_contribution": s.revenue_contribution,
            "conversion_rate": s.conversion_rate,
            "avg_ltv": s.avg_ltv,
            "platforms": s.platforms,
            "loyalty_score": s.conversion_rate * 10, # Re-using proxy from referral engine
        }
        for s in audience_segments
    ]

    await db.execute(delete(SponsorTarget).where(SponsorTarget.brand_id == brand_id))

    count = 0
    for sp in potential_sponsors:
        target = identify_sponsor_targets(
            brand_id=brand_id,
            potential_sponsors=[sp],
            brand_audience_data=brand_audience_data,
        )
        if target["target_company_name"] == "N/A":
            continue
        db.add(
            SponsorTarget(
                brand_id=brand_id,
                target_company_name=target["target_company_name"],
                industry=target["industry"],
                contact_info=target["contact_info"],
                estimated_deal_value=target["estimated_deal_value"],
                fit_score=target["fit_score"],
                confidence=target["confidence"],
                explanation=target["explanation"],
            )
        )
        count += 1
    await db.flush()
    return {"sponsor_targets_count": count}


async def get_sponsor_targets(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(SponsorTarget)
            .where(SponsorTarget.brand_id == brand_id, SponsorTarget.is_active.is_(True))
            .order_by(SponsorTarget.fit_score.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "target_company_name": r.target_company_name,
            "industry": r.industry,
            "contact_info": r.contact_info,
            "estimated_deal_value": r.estimated_deal_value,
            "fit_score": r.fit_score,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def recompute_sponsor_outreach_sequences(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    sponsor_targets = list(
        (await db.execute(select(SponsorTarget).where(SponsorTarget.brand_id == brand_id, SponsorTarget.is_active.is_(True))))
        .scalars()
        .all()
    )

    # DATA BOUNDARY: Static outreach templates — no live template/CRM integration yet.
    outreach_templates = [
        {
            'name': 'Tech Enterprise Outreach',
            'steps': [
                {'order': 1, 'type': 'email', 'content': 'Personalized email to Tech VP'},
                {'order': 2, 'type': 'linkedin_message', 'content': 'LinkedIn connection request'},
                {'order': 3, 'type': 'email', 'content': 'Follow-up with case study'},
            ],
            'effectiveness': 0.15,
            'target_industry': 'tech',
            'target_company_size_category': 'enterprise',
        },
        {
            'name': 'SMB Fashion Outreach',
            'steps': [
                {'order': 1, 'type': 'email', 'content': 'Introductory email to Fashion Brand Manager'},
                {'order': 2, 'type': 'email', 'content': 'Follow-up with lookbook'},
            ],
            'effectiveness': 0.10,
            'target_industry': 'fashion',
            'target_company_size_category': 'smb',
        },
        {
            'name': 'Standard Cold Outreach',
            'steps': [
                {'order': 1, 'type': 'email', 'content': 'Initial cold email'},
                {'order': 2, 'type': 'email', 'content': 'Second cold email'},
            ],
            'effectiveness': 0.05,
            'target_industry': '',
            'target_company_size_category': '',
        },
    ]

    # DATA BOUNDARY: Static outreach performance benchmarks — no live CRM data yet.
    historical_outreach_performance = [
        {'sequence_name': 'Tech Enterprise Outreach', 'response_rate': 0.18, 'conversion_rate': 0.03, 'industry': 'tech', 'company_size_category': 'enterprise'},
        {'sequence_name': 'SMB Fashion Outreach', 'response_rate': 0.12, 'conversion_rate': 0.02, 'industry': 'fashion', 'company_size_category': 'smb'},
        {'sequence_name': 'Standard Cold Outreach', 'response_rate': 0.06, 'conversion_rate': 0.01, 'industry': '', 'company_size_category': '',},
    ]

    await db.execute(delete(SponsorOutreachSequence).where(SponsorOutreachSequence.sponsor_target_id.in_([t.id for t in sponsor_targets])))

    outreach_sequences_count = 0
    for target in sponsor_targets:
        sequence = generate_sponsor_outreach_sequence(
            sponsor_target_id=target.id,
            target_company_name=target.target_company_name,
            target_company_industry=target.industry, # New parameter
            estimated_deal_value=target.estimated_deal_value, # New parameter
            outreach_templates=outreach_templates,
            historical_outreach_performance=historical_outreach_performance,
        )
        db.add(
            SponsorOutreachSequence(
                sponsor_target_id=target.id,
                sequence_name=sequence["sequence_name"],
                steps=sequence["steps"],
                estimated_response_rate=sequence["estimated_response_rate"],
                expected_value=sequence["expected_value"], # New field
                confidence=sequence["confidence"],
                explanation=sequence["explanation"], # New field
            )
        )
        outreach_sequences_count += 1

    await db.flush()
    return {"sponsor_outreach_sequences_count": outreach_sequences_count}


async def get_sponsor_outreach_sequences(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(SponsorOutreachSequence)
            .join(SponsorTarget)
            .where(SponsorTarget.brand_id == brand_id, SponsorOutreachSequence.is_active.is_(True))
            .order_by(SponsorOutreachSequence.created_at.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "sponsor_target_id": str(r.sponsor_target_id),
            "sequence_name": r.sequence_name,
            "steps": r.steps,
            "estimated_response_rate": r.estimated_response_rate,
            "expected_value": r.expected_value, # New field
            "confidence": r.confidence,
            "explanation": r.explanation, # New field
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def recompute_profit_guardrail_reports(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Derive financial metrics from real offer / audience data
    offers = list(
        (await db.execute(
            select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
        )).scalars().all()
    )
    segments = list(
        (await db.execute(
            select(AudienceSegment).where(
                AudienceSegment.brand_id == brand_id,
                AudienceSegment.is_active.is_(True),
            )
        )).scalars().all()
    )

    total_revenue = sum(getattr(s, "revenue_contribution", 0) or 0 for s in segments)
    total_audience = sum(getattr(s, "estimated_size", 0) or 0 for s in segments)
    avg_ltv = (
        sum((getattr(s, "avg_ltv", 0) or 0) * (getattr(s, "estimated_size", 0) or 0) for s in segments)
        / max(1, total_audience)
    ) if total_audience else 0

    avg_payout = sum(getattr(o, "payout_amount", 0) or 0 for o in offers) / max(1, len(offers)) if offers else 0
    avg_cvr = sum(getattr(o, "conversion_rate", 0) or 0 for o in offers) / max(1, len(offers)) if offers else 0

    # Build financial metrics from available data
    estimated_cac = avg_payout / max(avg_cvr, 0.001)
    profit_margin = max(0, (total_revenue - estimated_cac * total_audience * 0.01) / max(total_revenue, 1))
    refund_rate = 0.04  # default assumption; no refund data available yet
    ltv_to_cac = avg_ltv / max(estimated_cac, 1)

    financial_metrics = [
        {"metric_name": "profit_margin", "value": round(profit_margin, 4)},
        {"metric_name": "customer_acquisition_cost", "value": round(estimated_cac, 2)},
        {"metric_name": "monthly_burn_rate", "value": round(estimated_cac * total_audience * 0.005, 2)},
        {"metric_name": "refund_rate", "value": refund_rate},
        {"metric_name": "ltv_to_cac_ratio", "value": round(ltv_to_cac, 2)},
    ]

    await db.execute(delete(ProfitGuardrailReport).where(ProfitGuardrailReport.brand_id == brand_id))

    reports = analyze_profit_guardrails(
        brand_id=brand_id,
        financial_metrics=financial_metrics,
        defined_guardrails=[],  # use engine defaults
    )

    for report in reports:
        db.add(
            ProfitGuardrailReport(
                brand_id=brand_id,
                metric_name=report["metric_name"],
                current_value=report["current_value"],
                threshold_value=report["threshold_value"],
                status=report["status"],
                action_recommended=report["action_recommended"],
                estimated_impact=report["estimated_impact"],
                confidence=report["confidence"],
            )
        )
    await db.flush()
    return {"profit_guardrail_reports_count": len(reports)}


async def get_profit_guardrail_reports(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(ProfitGuardrailReport)
            .where(ProfitGuardrailReport.brand_id == brand_id, ProfitGuardrailReport.is_active.is_(True))
            .order_by(ProfitGuardrailReport.created_at.desc())
        ))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "brand_id": str(r.brand_id),
            "metric_name": r.metric_name,
            "current_value": r.current_value,
            "threshold_value": r.threshold_value,
            "status": r.status,
            "action_recommended": r.action_recommended,
            "estimated_impact": r.estimated_impact,
            "confidence": r.confidence,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]
