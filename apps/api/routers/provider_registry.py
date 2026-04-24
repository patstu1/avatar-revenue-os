"""Provider Registry — API endpoints for provider inventory, readiness, dependencies, blockers."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.provider_registry import (
    AuditSummaryOut,
    ProviderBlockerOut,
    ProviderDependencyOut,
    ProviderEntryOut,
    ProviderReadinessOut,
)
from apps.api.services import provider_registry_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/providers", response_model=list[ProviderEntryOut])
async def list_providers(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_providers(db)


@router.get("/{brand_id}/providers/readiness", response_model=list[ProviderReadinessOut])
async def list_readiness(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_readiness(db, brand_id)


@router.get("/{brand_id}/providers/dependencies", response_model=list[ProviderDependencyOut])
async def list_dependencies(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_dependencies(db)


@router.post("/{brand_id}/providers/audit", response_model=AuditSummaryOut)
async def audit_providers(
    brand_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.audit_providers(db, brand_id)
        return AuditSummaryOut(
            status="completed",
            providers_audited=result["providers_audited"],
            capabilities_written=result["capabilities_written"],
            dependencies_written=result["dependencies_written"],
            readiness_reports_written=result["readiness_reports_written"],
            blockers_found=result["blockers_found"],
            detail=f"Audited {result['providers_audited']} providers, {result['blockers_found']} blockers found",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/providers/blockers", response_model=list[ProviderBlockerOut])
async def list_blockers(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_blockers(db, brand_id)
