"""Buffer Distribution Layer — API endpoints for profiles, publish jobs, sync, blockers."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.buffer_distribution import (
    BufferBlockerOut,
    BufferProfileCreate,
    BufferProfileOut,
    BufferProfileUpdate,
    BufferPublishJobOut,
    BufferStatusSyncOut,
    RecomputeSummaryOut,
)
from apps.api.services import buffer_distribution_service as svc
from packages.db.models.core import Brand

router = APIRouter()
router_root = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


# ── Buffer Profiles (brand-scoped) ────────────────────────────────────

@router.get("/{brand_id}/buffer-profiles", response_model=list[BufferProfileOut])
async def list_buffer_profiles(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_buffer_profiles(db, brand_id, limit=limit)


@router.post("/{brand_id}/buffer-profiles", response_model=BufferProfileOut, status_code=status.HTTP_201_CREATED)
async def create_buffer_profile(
    brand_id: uuid.UUID, body: BufferProfileCreate,
    current_user: OperatorUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.create_buffer_profile(db, brand_id, body.model_dump())


# ── Buffer Profile Update (root-scoped) ──────────────────────────────

@router_root.patch("/buffer-profiles/{profile_id}", response_model=BufferProfileOut)
async def update_buffer_profile(
    profile_id: uuid.UUID, body: BufferProfileUpdate,
    current_user: OperatorUser, db: DBSession,
):
    result = await svc.update_buffer_profile(db, profile_id, body.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Buffer profile not found")
    return result


# ── Buffer Publish Jobs (brand-scoped) ────────────────────────────────

@router.get("/{brand_id}/buffer-publish-jobs", response_model=list[BufferPublishJobOut])
async def list_publish_jobs(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_publish_jobs(db, brand_id, limit=limit)


@router.post("/{brand_id}/buffer-publish-jobs/recompute", response_model=RecomputeSummaryOut)
async def recompute_publish_jobs(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_publish_jobs(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Buffer publish jobs — {result.get('jobs_created', 0)} created",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Buffer Job Submit (root-scoped) ───────────────────────────────────

@router_root.post("/buffer-publish-jobs/{job_id}/submit", response_model=RecomputeSummaryOut)
async def submit_publish_job(
    job_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
):
    try:
        result = await svc.submit_job_to_buffer(db, job_id)
        return RecomputeSummaryOut(
            status="completed" if result.get("success") else "failed",
            detail=f"Buffer submit — {result.get('status', 'unknown')}",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Buffer Status Sync (brand-scoped) ─────────────────────────────────

@router.post("/{brand_id}/buffer-status-sync/recompute", response_model=RecomputeSummaryOut)
async def recompute_status_sync(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.run_status_sync(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Buffer sync — {result.get('jobs_updated', 0)} updated, {result.get('jobs_published', 0)} published",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Buffer Blockers (brand-scoped) ────────────────────────────────────

@router.get("/{brand_id}/buffer-blockers", response_model=list[BufferBlockerOut])
async def list_buffer_blockers(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_buffer_blockers(db, brand_id, limit=limit)
