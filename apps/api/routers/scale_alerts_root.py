"""Alternate paths: POST /api/v1/alerts/{id}/acknowledge|resolve (same behavior as under /brands)."""

import uuid

from fastapi import APIRouter, HTTPException, status

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.scale_alerts import AlertResponse, ResolveRequest
from apps.api.services import scale_alerts_service as sas
from apps.api.services.audit_service import log_action

router = APIRouter()


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert_root(alert_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    alert, err = await sas.acknowledge_alert(db, alert_id, current_user.organization_id)
    if err == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Alert not accessible")
    await log_action(
        db,
        "alert.acknowledged",
        organization_id=current_user.organization_id,
        brand_id=alert.brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="operator_alert",
        entity_id=alert_id,
    )
    return sas._ser_alert(alert)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert_root(alert_id: uuid.UUID, body: ResolveRequest, current_user: CurrentUser, db: DBSession):
    alert, err = await sas.resolve_alert(db, alert_id, current_user.organization_id, notes=body.notes)
    if err == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Alert not accessible")
    await log_action(
        db,
        "alert.resolved",
        organization_id=current_user.organization_id,
        brand_id=alert.brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="operator_alert",
        entity_id=alert_id,
        details={"notes": body.notes},
    )
    return sas._ser_alert(alert)
