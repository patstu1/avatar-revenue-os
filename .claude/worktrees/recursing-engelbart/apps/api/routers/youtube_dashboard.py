"""YouTube dashboard — aggregated YouTube account health, publish results, and quota."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, and_

from apps.api.deps import CurrentUser, DBSession
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Brand
from packages.db.models.accounts import CreatorAccount
from packages.db.models.publishing import PublishJob, PerformanceMetric
from packages.db.enums import Platform

router = APIRouter()
brand_service = CRUDService(Brand)

DAILY_UPLOAD_LIMIT = 6


def _token_health(account: CreatorAccount) -> str:
    if account.credential_status == "disconnected" or not account.platform_access_token:
        return "disconnected"
    if not account.platform_token_expires_at:
        return "unknown"
    now = datetime.now(timezone.utc)
    if account.platform_token_expires_at < now:
        return "expired"
    if account.platform_token_expires_at < now + timedelta(days=3):
        return "expiring"
    return "healthy"


@router.get("/dashboard")
async def youtube_dashboard(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Fetch YouTube accounts for this brand
    result = await db.execute(
        select(CreatorAccount).where(
            and_(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.platform == Platform.YOUTUBE,
                CreatorAccount.is_active == True,
            )
        )
    )
    accounts = result.scalars().all()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    account_data = []
    total_uploads_today = 0

    for acct in accounts:
        # Last publish job
        pj_result = await db.execute(
            select(PublishJob)
            .where(
                and_(
                    PublishJob.creator_account_id == acct.id,
                    PublishJob.platform == Platform.YOUTUBE,
                )
            )
            .order_by(PublishJob.created_at.desc())
            .limit(1)
        )
        last_publish = pj_result.scalar_one_or_none()

        # Count today's uploads
        today_count_result = await db.execute(
            select(func.count()).select_from(PublishJob).where(
                and_(
                    PublishJob.creator_account_id == acct.id,
                    PublishJob.platform == Platform.YOUTUBE,
                    PublishJob.created_at >= today_start,
                )
            )
        )
        uploads_today = today_count_result.scalar() or 0
        total_uploads_today += uploads_today

        # Latest performance metric
        pm_result = await db.execute(
            select(PerformanceMetric)
            .where(
                and_(
                    PerformanceMetric.creator_account_id == acct.id,
                    PerformanceMetric.platform == Platform.YOUTUBE,
                )
            )
            .order_by(PerformanceMetric.measured_at.desc())
            .limit(1)
        )
        latest_metric = pm_result.scalar_one_or_none()

        health = _token_health(acct)
        upload_ready = (
            acct.credential_status == "connected"
            and health in ("healthy", "expiring")
            and uploads_today < DAILY_UPLOAD_LIMIT
        )

        account_data.append({
            "id": str(acct.id),
            "platform_username": acct.platform_username,
            "credential_status": acct.credential_status or "not_connected",
            "token_expires_at": acct.platform_token_expires_at.isoformat() if acct.platform_token_expires_at else None,
            "token_health": health,
            "follower_count": acct.follower_count,
            "last_synced_at": acct.last_synced_at.isoformat() if acct.last_synced_at else None,
            "upload_ready": upload_ready,
            "uploads_today": uploads_today,
            "last_publish": {
                "status": last_publish.status.value if last_publish and hasattr(last_publish.status, 'value') else str(last_publish.status) if last_publish else None,
                "platform_post_url": last_publish.platform_post_url if last_publish else None,
                "published_at": last_publish.published_at.isoformat() if last_publish and last_publish.published_at else None,
                "error_message": last_publish.error_message if last_publish else None,
            } if last_publish else None,
            "recent_metrics": {
                "views": latest_metric.views if latest_metric else 0,
                "likes": latest_metric.likes if latest_metric else 0,
                "comments": latest_metric.comments if latest_metric else 0,
                "watch_time_seconds": latest_metric.watch_time_seconds if latest_metric else 0,
                "rpm": round(latest_metric.rpm, 2) if latest_metric else 0,
                "engagement_rate": round(latest_metric.engagement_rate, 4) if latest_metric else 0,
            } if latest_metric else None,
        })

    return {
        "accounts": account_data,
        "quota": {
            "daily_upload_limit": DAILY_UPLOAD_LIMIT,
            "uploads_today": total_uploads_today,
            "remaining": max(0, DAILY_UPLOAD_LIMIT * len(accounts) - total_uploads_today),
        },
    }
