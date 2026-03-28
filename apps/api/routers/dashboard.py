"""Dashboard overview endpoint — reads real persisted data."""
from sqlalchemy import func, select

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.dashboard import DashboardOverview
from fastapi import APIRouter

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
