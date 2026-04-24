"""Scale alerts, launch candidates, blockers, readiness, notifications.
POST recompute writes. All GETs are read-only. Acknowledge/resolve are targeted mutations.

Note: avoid ``from __future__ import annotations`` here so FastAPI resolves Annotated deps
(CurrentUser, OperatorUser, DBSession) correctly.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.scale_alerts import (
    AlertResponse, LaunchCandidateResponse, BlockerResponse,
    ReadinessResponse, NotificationResponse, ResolveRequest,
)
from apps.api.services import scale_alerts_service as sas
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()

async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand

@router.get("/{brand_id}/alerts", response_model=list[AlertResponse])
async def list_alerts(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    status: Optional[str] = Query(None, description="Filter by unread | acknowledged | resolved"),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, description="critical | high | medium | low"),
):
    await _require_brand(brand_id, current_user, db)
    return await sas.get_alerts(db, brand_id, status=status, alert_type=alert_type, severity=severity)

@router.post("/{brand_id}/alerts/recompute")
async def recompute_alerts(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await sas.recompute_alerts(db, brand_id)
    await log_action(db, "scale_alerts.recomputed", organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id, actor_type="human", entity_type="operator_alert", details=result)
    return result


@router.post("/{brand_id}/scale-intel/recompute-all")
async def recompute_scale_intel_all(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    """Launch candidates first (so alerts can link), then alerts, blockers, readiness."""
    await _require_brand(brand_id, current_user, db)
    lc = await sas.recompute_launch_candidates(db, brand_id)
    al = await sas.recompute_alerts(db, brand_id)
    sb = await sas.recompute_scale_blockers(db, brand_id)
    lr = await sas.recompute_launch_readiness(db, brand_id)
    await log_action(
        db, "scale_intel.recomputed_all",
        organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="scale_intel", details={"launch_candidates": lc, "alerts": al, "blockers": sb, "readiness": lr},
    )
    return {"launch_candidates": lc, "alerts": al, "scale_blockers": sb, "launch_readiness": lr}

@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    alert, err = await sas.acknowledge_alert(db, alert_id, current_user.organization_id)
    if err == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Alert not accessible")
    await log_action(db, "alert.acknowledged", organization_id=current_user.organization_id, brand_id=alert.brand_id, user_id=current_user.id, actor_type="human", entity_type="operator_alert", entity_id=alert_id)
    return sas._ser_alert(alert)

@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: uuid.UUID, body: ResolveRequest, current_user: CurrentUser, db: DBSession):
    alert, err = await sas.resolve_alert(db, alert_id, current_user.organization_id, notes=body.notes)
    if err == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Alert not accessible")
    await log_action(db, "alert.resolved", organization_id=current_user.organization_id, brand_id=alert.brand_id, user_id=current_user.id, actor_type="human", entity_type="operator_alert", entity_id=alert_id, details={"notes": body.notes})
    return sas._ser_alert(alert)

@router.get("/{brand_id}/launch-candidates", response_model=list[LaunchCandidateResponse])
async def list_launch_candidates(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await sas.get_launch_candidates(db, brand_id)

@router.post("/{brand_id}/launch-candidates/recompute")
async def recompute_launch_candidates(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await sas.recompute_launch_candidates(db, brand_id)
    await log_action(db, "launch_candidates.recomputed", organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id, actor_type="human", entity_type="launch_candidate", details=result)
    return result

@router.get("/launch-candidates/{candidate_id}", response_model=LaunchCandidateResponse)
async def get_launch_candidate(candidate_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    c, err = await sas.get_launch_candidate_detail(db, candidate_id, current_user.organization_id)
    if err == "not_found":
        raise HTTPException(status_code=404, detail="Launch candidate not found")
    if err == "forbidden":
        raise HTTPException(status_code=403, detail="Launch candidate not accessible")
    return c

@router.get("/{brand_id}/scale-blockers", response_model=list[BlockerResponse])
async def list_scale_blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await sas.get_scale_blockers(db, brand_id)

@router.post("/{brand_id}/scale-blockers/recompute")
async def recompute_scale_blockers(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await sas.recompute_scale_blockers(db, brand_id)
    await log_action(db, "scale_blockers.recomputed", organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id, actor_type="human", entity_type="scale_blocker", details=result)
    return result

@router.get("/{brand_id}/launch-readiness", response_model=ReadinessResponse)
async def get_launch_readiness(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    r = await sas.get_launch_readiness(db, brand_id)
    if not r:
        raise HTTPException(status_code=404, detail="No readiness report — run recompute first")
    return r

@router.post("/{brand_id}/launch-readiness/recompute")
async def recompute_launch_readiness(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await sas.recompute_launch_readiness(db, brand_id)
    await log_action(db, "launch_readiness.recomputed", organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id, actor_type="human", entity_type="launch_readiness", details=result)
    return result

@router.get("/{brand_id}/notifications", response_model=list[NotificationResponse])
async def list_notifications(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await sas.get_notifications(db, brand_id)
