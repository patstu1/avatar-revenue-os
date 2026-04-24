"""Dashboard overview endpoint — reads real persisted data."""
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.dashboard import DashboardOverview
from apps.api.schemas.growth import (
    AudienceSegmentResponse,
    ExpansionRecommendationsResponse,
    GeoLanguageRecRow,
    GrowthIntelDashboardResponse,
    LeaksDashboardResponse,
    LtvModelResponse,
    PaidAmplificationResponse,
    PaidJobRow,
    RevenueLeakRow,
    TrustReportRow,
    TrustSignalsResponse,
)
from apps.api.schemas.revenue_intel import MonetizationRecRow, RevenueIntelDashboardResponse
from apps.api.schemas.scale import ScaleCommandCenterResponse
from apps.api.services import growth_service as growth_svc
from apps.api.services import revenue_service as rev_svc
from apps.api.services import scale_service as scale_svc
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Avatar, Brand
from packages.db.models.offers import Offer
from packages.db.models.publishing import PublishJob
from packages.db.models.system import AuditLog, ProviderUsageCost, SystemJob

router = APIRouter()


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(current_user: CurrentUser, db: DBSession):
    org_id = current_user.organization_id

    brand_ids_q = select(Brand.id).where(Brand.organization_id == org_id)

    brands_count = (await db.execute(
        select(func.count()).select_from(Brand).where(Brand.organization_id == org_id)
    )).scalar() or 0

    avatars_count = (await db.execute(
        select(func.count()).select_from(Avatar).where(Avatar.brand_id.in_(brand_ids_q))
    )).scalar() or 0

    offers_count = (await db.execute(
        select(func.count()).select_from(Offer).where(Offer.brand_id.in_(brand_ids_q))
    )).scalar() or 0

    accounts_count = (await db.execute(
        select(func.count()).select_from(CreatorAccount).where(CreatorAccount.brand_id.in_(brand_ids_q))
    )).scalar() or 0

    content_count = (await db.execute(
        select(func.count()).select_from(ContentItem).where(ContentItem.brand_id.in_(brand_ids_q))
    )).scalar() or 0

    publish_count = (await db.execute(
        select(func.count()).select_from(PublishJob).where(PublishJob.brand_id.in_(brand_ids_q))
    )).scalar() or 0

    audit_count = (await db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.organization_id == org_id)
    )).scalar() or 0

    jobs_count = (await db.execute(select(func.count()).select_from(SystemJob))).scalar() or 0

    total_cost = (await db.execute(
        select(func.coalesce(func.sum(ProviderUsageCost.cost), 0.0)).where(
            ProviderUsageCost.brand_id.in_(brand_ids_q)
        )
    )).scalar() or 0.0

    platform_q = await db.execute(
        select(CreatorAccount.platform, func.count())
        .where(CreatorAccount.brand_id.in_(brand_ids_q), CreatorAccount.is_active.is_(True))
        .group_by(CreatorAccount.platform)
    )
    active_by_platform = {str(row[0].value): row[1] for row in platform_q.all()}

    recent_audit_q = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    recent_audits = [
        {"action": a.action, "actor_type": a.actor_type, "entity_type": a.entity_type, "created_at": str(a.created_at)}
        for a in recent_audit_q.scalars().all()
    ]

    recent_jobs_q = await db.execute(
        select(SystemJob).order_by(SystemJob.created_at.desc()).limit(10)
    )
    recent_jobs = [
        {"job_name": j.job_name, "status": j.status.value if hasattr(j.status, 'value') else str(j.status), "queue": j.queue, "created_at": str(j.created_at)}
        for j in recent_jobs_q.scalars().all()
    ]

    return DashboardOverview(
        total_brands=brands_count,
        total_avatars=avatars_count,
        total_offers=offers_count,
        total_creator_accounts=accounts_count,
        total_content_items=content_count,
        total_publish_jobs=publish_count,
        total_audit_entries=audit_count,
        total_system_jobs=jobs_count,
        total_provider_cost=float(total_cost),
        active_accounts_by_platform=active_by_platform,
        recent_audit_actions=recent_audits,
        recent_jobs=recent_jobs,
    )


@router.get("/scale-command-center", response_model=ScaleCommandCenterResponse)
async def get_scale_command_center(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(..., description="Brand to render command center for"),
):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")
    try:
        payload = await scale_svc.build_scale_command_center(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    return ScaleCommandCenterResponse(**payload)


@router.get("/leaks", response_model=LeaksDashboardResponse)
async def get_revenue_leaks_dashboard(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(..., description="Brand for funnel + leak rows"),
):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")
    try:
        data = await growth_svc.get_leak_reports_dashboard(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    return LeaksDashboardResponse(
        brand_id=data["brand_id"],
        funnel=data.get("funnel") or {},
        leaks=[RevenueLeakRow(**x) for x in data["leaks"]],
        summary=data.get("summary") or {},
    )


@router.get("/growth-intel", response_model=GrowthIntelDashboardResponse)
async def get_growth_intel_full_dashboard(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(..., description="Brand for Phase 6 growth intel (read-only)"),
):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")
    try:
        raw = await growth_svc.get_growth_intel_dashboard(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    leaks = raw["leaks"]
    exp = raw["expansion"]
    paid = raw["paid_amplification"]
    trust = raw["trust_signals"]
    return GrowthIntelDashboardResponse(
        brand_id=raw["brand_id"],
        audience_segments=[AudienceSegmentResponse.model_validate(x) for x in raw["audience_segments"]],
        ltv_models=[LtvModelResponse.model_validate(x) for x in raw["ltv_models"]],
        leaks=LeaksDashboardResponse(
            brand_id=leaks["brand_id"],
            funnel=leaks.get("funnel") or {},
            leaks=[RevenueLeakRow(**x) for x in leaks["leaks"]],
            summary=leaks.get("summary") or {},
        ),
        expansion=ExpansionRecommendationsResponse(
            geo_language_recommendations=[GeoLanguageRecRow(**g) for g in exp["geo_language_recommendations"]],
            cross_platform_flow_plans=exp["cross_platform_flow_plans"],
            latest_expansion_decision_id=exp.get("latest_expansion_decision_id"),
        ),
        paid_amplification=PaidAmplificationResponse(
            jobs=[PaidJobRow(**j) for j in paid["jobs"]],
            note=paid.get("note", ""),
        ),
        trust_signals=TrustSignalsResponse(reports=[TrustReportRow(**r) for r in trust["reports"]]),
    )


@router.get("/revenue-intel", response_model=RevenueIntelDashboardResponse)
async def get_revenue_intel_dashboard(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(..., description="Brand for revenue intelligence (read-only)"),
):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")
    try:
        raw = await rev_svc.get_revenue_intel_dashboard(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    return RevenueIntelDashboardResponse(
        brand_id=raw["brand_id"],
        offer_stacks=[MonetizationRecRow(**r) for r in raw["offer_stacks"]],
        funnel_paths=[MonetizationRecRow(**r) for r in raw["funnel_paths"]],
        owned_audience=[MonetizationRecRow(**r) for r in raw["owned_audience"]],
        productization=[MonetizationRecRow(**r) for r in raw["productization"]],
        density_improvements=[MonetizationRecRow(**r) for r in raw["density_improvements"]],
    )
