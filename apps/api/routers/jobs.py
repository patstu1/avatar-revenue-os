"""System job monitoring endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import CurrentUser, DBSession
from apps.api.services.crud_service import CRUDService
from packages.db.models.system import AuditLog, ProviderUsageCost, SystemJob

router = APIRouter()
job_service = CRUDService(SystemJob)
audit_service = CRUDService(AuditLog)
cost_service = CRUDService(ProviderUsageCost)


@router.get("/")
async def list_jobs(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    from apps.api.deps import require_brand_access

    if brand_id:
        await require_brand_access(brand_id, current_user, db)
    filters = {"organization_id": current_user.organization_id}
    if brand_id:
        filters["brand_id"] = brand_id
    if status:
        filters["status"] = status
    return await job_service.list(db, filters=filters, page=page, page_size=page_size)


@router.get("/audit/logs")
async def list_audit_logs(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    return await audit_service.list(
        db,
        filters={"organization_id": current_user.organization_id},
        page=page,
        page_size=page_size,
    )


@router.get("/costs/providers")
async def list_provider_costs(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
):
    from apps.api.deps import require_brand_access

    if brand_id:
        await require_brand_access(brand_id, current_user, db)
    filters = {"organization_id": current_user.organization_id}
    if brand_id:
        filters["brand_id"] = brand_id
    return await cost_service.list(db, filters=filters, page=page)


@router.get("/{job_id}")
async def get_job(job_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        job = await job_service.get_or_404(db, job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
