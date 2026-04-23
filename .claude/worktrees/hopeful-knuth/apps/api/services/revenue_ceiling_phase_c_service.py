"""Revenue Ceiling Phase C — recurring revenue, sponsor inventory, trust conversion,
monetization mix, paid promotion."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.quality import QAReport
from packages.db.models.revenue_ceiling_phase_b import ProductOpportunity
from packages.db.models.revenue_ceiling_phase_c import (
    MonetizationMixReport,
    PaidPromotionCandidate,
    RecurringRevenueModel,
    SponsorInventory,
    SponsorPackageRecommendation,
    TrustConversionReport,
)
from packages.scoring.revenue_ceiling_phase_c_engines import (
    RC_PHASE_C,
    evaluate_paid_promotion_candidate,
    score_monetization_mix,
    score_recurring_revenue,
    score_sponsor_inventory_item,
    score_sponsor_package,
    score_trust_conversion,
)

# ---------------------------------------------------------------------------
# ContentType → sponsor engine content-type mapping
# ---------------------------------------------------------------------------

_CONTENT_TYPE_MAP: dict[str, str] = {
    "long_video": "long_form",
    "live_stream": "long_form",
    "short_video": "short_form",
    "static_image": "short_form",
    "carousel": "short_form",
    "story": "short_form",
    "text_post": "article",
}


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != RC_PHASE_C}


# ---------------------------------------------------------------------------
# Recompute functions
# ---------------------------------------------------------------------------


async def recompute_recurring_revenue(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Active offers — payout_amount is the key signal
    offers = list(
        (
            await db.execute(
                select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    offer_dicts = [
        {
            "id": str(o.id),
            "name": o.name,
            "payout_amount": float(o.payout_amount or 0),
            "monetization_method": getattr(
                o.monetization_method, "value", str(o.monetization_method)
            ),
        }
        for o in offers
    ]

    # Audience size from creator accounts
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(
                CreatorAccount.brand_id == brand_id
            )
        )
    ).scalar()
    audience_size = int(aud_scalar or 0)

    # Average content engagement rate
    eng_scalar = (
        await db.execute(
            select(func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_engagement = float(eng_scalar or 0.04)

    # Existing product types from Phase B ProductOpportunity
    product_type_rows = list(
        (
            await db.execute(
                select(ProductOpportunity.product_type).where(
                    ProductOpportunity.brand_id == brand_id,
                    ProductOpportunity.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    existing_recurring_products = [pt for pt in product_type_rows if pt]

    result = score_recurring_revenue(
        brand_niche=brand.niche or "general",
        offers=offer_dicts,
        audience_size=audience_size,
        avg_content_engagement_rate=avg_engagement,
        existing_recurring_products=existing_recurring_products,
    )
    r = _strip_meta(result)

    await db.execute(
        delete(RecurringRevenueModel).where(RecurringRevenueModel.brand_id == brand_id)
    )
    db.add(
        RecurringRevenueModel(
            brand_id=brand_id,
            recurring_potential_score=float(r["recurring_potential_score"]),
            best_recurring_offer_type=r["best_recurring_offer_type"],
            audience_fit=float(r["audience_fit"]),
            churn_risk_proxy=float(r["churn_risk_proxy"]),
            expected_monthly_value=float(r["expected_monthly_value"]),
            expected_annual_value=float(r["expected_annual_value"]),
            confidence=float(r["confidence"]),
            explanation=r.get("explanation"),
        )
    )
    await db.flush()
    return {"recurring_revenue_rows": 1}


async def recompute_sponsor_inventory(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Content items (limit 100)
    items = list(
        (
            await db.execute(
                select(ContentItem).where(ContentItem.brand_id == brand_id).limit(100)
            )
        )
        .scalars()
        .all()
    )

    # Per-item performance aggregates
    agg_rows = (
        await db.execute(
            select(
                PerformanceMetric.content_item_id,
                func.coalesce(func.sum(PerformanceMetric.impressions), 0).label("imp"),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04).label("eng"),
            )
            .where(PerformanceMetric.brand_id == brand_id)
            .group_by(PerformanceMetric.content_item_id)
        )
    ).all()
    perf_map: dict[uuid.UUID, tuple[int, float]] = {
        row[0]: (int(row[1]), float(row[2])) for row in agg_rows
    }

    # Brand-level audience size
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(
                CreatorAccount.brand_id == brand_id
            )
        )
    ).scalar()
    audience_size = int(aud_scalar or 0)

    # Brand-level total impressions and avg engagement for package scoring
    brand_perf = (
        await db.execute(
            select(
                func.coalesce(func.sum(PerformanceMetric.impressions), 0).label("total_imp"),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04).label("avg_eng"),
            ).where(PerformanceMetric.brand_id == brand_id)
        )
    ).first()
    total_impressions = int(brand_perf[0] if brand_perf else 0)
    avg_engagement = float(brand_perf[1] if brand_perf else 0.04)

    # Score each content item and collect for package input
    scored_pairs: list[tuple[ContentItem, dict[str, Any]]] = []
    for ci in items:
        imp, eng = perf_map.get(ci.id, (0, 0.04))
        ct_raw = (
            getattr(ci.content_type, "value", str(ci.content_type)) if ci.content_type else ""
        )
        ct = _CONTENT_TYPE_MAP.get(ct_raw, "short_form")
        row = score_sponsor_inventory_item(
            content_item_id=str(ci.id),
            content_title=ci.title,
            niche=brand.niche or "general",
            impressions=imp,
            engagement_rate=eng,
            audience_size=audience_size,
            content_type=ct,
        )
        stripped = _strip_meta(row)
        stripped["content_type"] = ct  # keep for _build_deliverables inside package scorer
        scored_pairs.append((ci, stripped))

    inv_dicts = [d for _, d in scored_pairs]

    # Brand-level sponsor package
    pkg_row = score_sponsor_package(
        brand_niche=brand.niche or "general",
        total_audience=audience_size,
        avg_monthly_impressions=total_impressions,
        avg_engagement_rate=avg_engagement,
        available_inventory=inv_dicts,
    )
    pkg_row = _strip_meta(pkg_row)

    # Delete stale rows
    await db.execute(delete(SponsorInventory).where(SponsorInventory.brand_id == brand_id))
    await db.execute(
        delete(SponsorPackageRecommendation).where(
            SponsorPackageRecommendation.brand_id == brand_id
        )
    )

    # Insert per-item inventory rows
    for ci, row in scored_pairs:
        pkg_name = f"{brand.niche or 'general'} × {row['sponsor_category'].replace('_', ' ').title()} Sponsor Package"
        db.add(
            SponsorInventory(
                brand_id=brand_id,
                content_item_id=ci.id,
                sponsor_fit_score=float(row["sponsor_fit_score"]),
                recommended_package_name=pkg_name,
                estimated_package_price=float(row["estimated_package_price"]),
                sponsor_category=row["sponsor_category"],
                confidence=float(row["confidence"]),
                explanation=row.get("explanation"),
            )
        )

    db.add(
        SponsorPackageRecommendation(
            brand_id=brand_id,
            recommended_package=pkg_row.get("recommended_package"),
            sponsor_fit_score=float(pkg_row.get("sponsor_fit_score", 0.0)),
            estimated_package_price=float(pkg_row.get("estimated_package_price", 0.0)),
            sponsor_category=str(pkg_row.get("sponsor_category", "general")),
            confidence=float(pkg_row.get("confidence", 0.0)),
            explanation=pkg_row.get("explanation"),
        )
    )
    await db.flush()
    return {"sponsor_inventory_rows": len(scored_pairs), "sponsor_package": 1}


async def recompute_trust_conversion(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Average quality score from QA reports (composite_score is the closest proxy)
    quality_scalar = (
        await db.execute(
            select(func.coalesce(func.avg(QAReport.composite_score), 0.5)).where(
                QAReport.brand_id == brand_id
            )
        )
    ).scalar()
    avg_quality = float(quality_scalar or 0.5)

    # Content item count
    content_count_scalar = (
        await db.execute(
            select(func.count(ContentItem.id)).where(ContentItem.brand_id == brand_id)
        )
    ).scalar()
    content_count = int(content_count_scalar or 0)

    # Derive trust signals from brand metadata and content volume
    has_testimonials = (
        bool(brand.tone_of_voice and "testimonial" in brand.tone_of_voice.lower())
        or content_count > 5
    )
    has_case_studies = content_count > 10
    social_proof_count = min(50, content_count)
    has_media_features = brand.description is not None
    has_certifications = False

    # Average offer conversion rate
    cvr_scalar = (
        await db.execute(
            select(func.coalesce(func.avg(Offer.conversion_rate), 0.02)).where(
                Offer.brand_id == brand_id, Offer.is_active.is_(True)
            )
        )
    ).scalar()
    avg_conversion_rate = float(cvr_scalar or 0.02)

    result = score_trust_conversion(
        brand_niche=brand.niche or "general",
        has_testimonials=has_testimonials,
        has_case_studies=has_case_studies,
        has_social_proof_count=social_proof_count,
        has_media_features=has_media_features,
        has_certifications=has_certifications,
        content_item_count=content_count,
        avg_quality_score=avg_quality,
        offer_conversion_rate=avg_conversion_rate,
    )
    r = _strip_meta(result)

    await db.execute(
        delete(TrustConversionReport).where(TrustConversionReport.brand_id == brand_id)
    )
    db.add(
        TrustConversionReport(
            brand_id=brand_id,
            trust_deficit_score=float(r["trust_deficit_score"]),
            recommended_proof_blocks=r.get("recommended_proof_blocks"),
            missing_trust_elements=r.get("missing_trust_elements"),
            expected_uplift=float(r["expected_uplift"]),
            confidence=float(r["confidence"]),
            explanation=r.get("explanation"),
        )
    )
    await db.flush()
    return {"trust_conversion_rows": 1}


async def recompute_monetization_mix(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # Active offers — needed for active_offer_types and fallback mix
    offers = list(
        (
            await db.execute(
                select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    active_offer_types = list(
        {getattr(o.monetization_method, "value", str(o.monetization_method)) for o in offers}
    )

    # Aggregate revenue by monetization method via ContentItem → PerformanceMetric
    agg_rows = (
        await db.execute(
            select(
                ContentItem.monetization_method,
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label("rev"),
            )
            .select_from(ContentItem)
            .join(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
            .where(ContentItem.brand_id == brand_id)
            .group_by(ContentItem.monetization_method)
        )
    ).all()

    revenue_by_method: dict[str, float] = {
        str(row[0] or "other"): float(row[1])
        for row in agg_rows
        if float(row[1]) > 0
    }

    # Fallback: equal weight splits across active offer types when no revenue data
    if not revenue_by_method:
        for method in active_offer_types:
            revenue_by_method[method] = 1.0

    total_revenue = sum(revenue_by_method.values())

    # Audience size
    aud_scalar = (
        await db.execute(
            select(func.coalesce(func.sum(CreatorAccount.follower_count), 0)).where(
                CreatorAccount.brand_id == brand_id
            )
        )
    ).scalar()
    audience_size = int(aud_scalar or 0)

    result = score_monetization_mix(
        brand_niche=brand.niche or "general",
        revenue_by_method=revenue_by_method,
        total_revenue=total_revenue,
        audience_size=audience_size,
        active_offer_types=active_offer_types,
    )
    r = _strip_meta(result)

    await db.execute(
        delete(MonetizationMixReport).where(MonetizationMixReport.brand_id == brand_id)
    )
    db.add(
        MonetizationMixReport(
            brand_id=brand_id,
            current_revenue_mix=r.get("current_revenue_mix"),
            dependency_risk=float(r["dependency_risk"]),
            underused_monetization_paths=r.get("underused_monetization_paths"),
            next_best_mix=r.get("next_best_mix"),
            expected_margin_uplift=float(r["expected_margin_uplift"]),
            expected_ltv_uplift=float(r["expected_ltv_uplift"]),
            confidence=float(r["confidence"]),
            explanation=r.get("explanation"),
        )
    )
    await db.flush()
    return {"monetization_mix_rows": 1}


async def recompute_paid_promotion_candidates(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    # All content items for brand (limit 200)
    items = list(
        (
            await db.execute(
                select(ContentItem).where(ContentItem.brand_id == brand_id).limit(200)
            )
        )
        .scalars()
        .all()
    )

    # Per-item aggregated performance
    agg_rows = (
        await db.execute(
            select(
                PerformanceMetric.content_item_id,
                func.coalesce(func.sum(PerformanceMetric.impressions), 0).label("imp"),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0).label("eng"),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0).label("rev"),
            )
            .where(PerformanceMetric.brand_id == brand_id)
            .group_by(PerformanceMetric.content_item_id)
        )
    ).all()
    perf_map: dict[uuid.UUID, tuple[int, float, float]] = {
        row[0]: (int(row[1]), float(row[2]), float(row[3])) for row in agg_rows
    }

    now = datetime.now(timezone.utc)

    await db.execute(
        delete(PaidPromotionCandidate).where(PaidPromotionCandidate.brand_id == brand_id)
    )

    n = 0
    eligible_count = 0
    for ci in items:
        imp, eng, rev = perf_map.get(ci.id, (0, 0.0, 0.0))
        total_cost = float(ci.total_cost or 0)
        roi = rev / max(total_cost, 1.0)

        ca = ci.created_at
        if ca is not None and ca.tzinfo is None:
            ca = ca.replace(tzinfo=timezone.utc)
        content_age_days = (now - ca).days if ca else 0

        row = evaluate_paid_promotion_candidate(
            content_item_id=str(ci.id),
            content_title=ci.title,
            organic_impressions=imp,
            organic_engagement_rate=eng,
            organic_revenue=rev,
            organic_roi=roi,
            content_age_days=content_age_days,
        )
        r = _strip_meta(row)

        is_elig = bool(r.get("is_eligible", False))
        if is_elig:
            eligible_count += 1

        db.add(
            PaidPromotionCandidate(
                brand_id=brand_id,
                content_item_id=ci.id,
                organic_winner_evidence=r.get("organic_winner_evidence"),
                is_eligible=is_elig,
                gate_reason=r.get("gate_reason"),
                confidence=float(r.get("confidence", 0.0)),
            )
        )
        n += 1

    await db.flush()
    return {"paid_promotion_rows": n, "eligible": eligible_count}


# ---------------------------------------------------------------------------
# Dict helpers (model → plain dict)
# ---------------------------------------------------------------------------


def _rrm_dict(x: RecurringRevenueModel) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "recurring_potential_score": x.recurring_potential_score,
        "best_recurring_offer_type": x.best_recurring_offer_type,
        "audience_fit": x.audience_fit,
        "churn_risk_proxy": x.churn_risk_proxy,
        "expected_monthly_value": x.expected_monthly_value,
        "expected_annual_value": x.expected_annual_value,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


def _si_dict(x: SponsorInventory) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "content_item_id": str(x.content_item_id) if x.content_item_id else None,
        "content_title": None,  # joined in getter
        "sponsor_fit_score": x.sponsor_fit_score,
        "recommended_package_name": x.recommended_package_name,
        "estimated_package_price": x.estimated_package_price,
        "sponsor_category": x.sponsor_category,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


def _spr_dict(x: SponsorPackageRecommendation) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "recommended_package": x.recommended_package,
        "sponsor_fit_score": x.sponsor_fit_score,
        "estimated_package_price": x.estimated_package_price,
        "sponsor_category": x.sponsor_category,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


def _tcr_dict(x: TrustConversionReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "trust_deficit_score": x.trust_deficit_score,
        "recommended_proof_blocks": x.recommended_proof_blocks,
        "missing_trust_elements": x.missing_trust_elements,
        "expected_uplift": x.expected_uplift,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


def _mmr_dict(x: MonetizationMixReport) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "current_revenue_mix": x.current_revenue_mix,
        "dependency_risk": x.dependency_risk,
        "underused_monetization_paths": x.underused_monetization_paths,
        "next_best_mix": x.next_best_mix,
        "expected_margin_uplift": x.expected_margin_uplift,
        "expected_ltv_uplift": x.expected_ltv_uplift,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


def _ppc_dict(x: PaidPromotionCandidate) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "content_item_id": str(x.content_item_id),
        "content_title": None,  # joined in getter
        "organic_winner_evidence": x.organic_winner_evidence,
        "is_eligible": x.is_eligible,
        "gate_reason": x.gate_reason,
        "confidence": x.confidence,
    }


# ---------------------------------------------------------------------------
# Getter functions
# ---------------------------------------------------------------------------


async def get_recurring_revenue(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(RecurringRevenueModel)
                .where(RecurringRevenueModel.brand_id == brand_id)
                .order_by(RecurringRevenueModel.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_rrm_dict(r) for r in rows]


async def get_sponsor_inventory(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(SponsorInventory)
                .where(SponsorInventory.brand_id == brand_id)
                .order_by(SponsorInventory.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return []
    ids = [r.content_item_id for r in rows if r.content_item_id]
    titles: dict[str, str] = {}
    if ids:
        title_rows = (
            await db.execute(
                select(ContentItem.id, ContentItem.title).where(ContentItem.id.in_(ids))
            )
        ).all()
        titles = {str(ci_id): t for ci_id, t in title_rows}
    out: list[dict[str, Any]] = []
    for r in rows:
        d = _si_dict(r)
        d["content_title"] = titles.get(str(r.content_item_id)) if r.content_item_id else None
        out.append(d)
    return out


async def get_sponsor_package_recommendations(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(SponsorPackageRecommendation)
                .where(SponsorPackageRecommendation.brand_id == brand_id)
                .order_by(SponsorPackageRecommendation.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_spr_dict(r) for r in rows]


async def get_trust_conversion(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(TrustConversionReport)
                .where(TrustConversionReport.brand_id == brand_id)
                .order_by(TrustConversionReport.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_tcr_dict(r) for r in rows]


async def get_monetization_mix(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(MonetizationMixReport)
                .where(MonetizationMixReport.brand_id == brand_id)
                .order_by(MonetizationMixReport.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_mmr_dict(r) for r in rows]


async def get_paid_promotion_candidates(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(PaidPromotionCandidate)
                .where(PaidPromotionCandidate.brand_id == brand_id)
                .order_by(PaidPromotionCandidate.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return []
    ids = [r.content_item_id for r in rows]
    title_rows = (
        await db.execute(
            select(ContentItem.id, ContentItem.title).where(ContentItem.id.in_(ids))
        )
    ).all()
    titles = {str(ci_id): t for ci_id, t in title_rows}
    out: list[dict[str, Any]] = []
    for r in rows:
        d = _ppc_dict(r)
        d["content_title"] = titles.get(str(r.content_item_id))
        out.append(d)
    return out
