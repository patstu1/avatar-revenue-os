"""Decision record endpoints — read-only access to persisted decision objects."""
import uuid

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import CurrentUser, DBSession
from apps.api.services.crud_service import CRUDService
from packages.db.models.decisions import (
    AllocationDecision,
    ExpansionDecision,
    MonetizationDecision,
    OpportunityDecision,
    PublishDecision,
    ScaleDecision,
    SuppressionDecision,
)

router = APIRouter()

DECISION_SERVICES = {
    "opportunity": CRUDService(OpportunityDecision),
    "monetization": CRUDService(MonetizationDecision),
    "publish": CRUDService(PublishDecision),
    "suppression": CRUDService(SuppressionDecision),
    "scale": CRUDService(ScaleDecision),
    "allocation": CRUDService(AllocationDecision),
    "expansion": CRUDService(ExpansionDecision),
}


@router.get("/{decision_type}")
async def list_decisions(
    decision_type: str,
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    service = DECISION_SERVICES.get(decision_type)
    if service is None:
        raise HTTPException(status_code=400, detail=f"Unknown decision type: {decision_type}")
    return await service.list(db, filters={"brand_id": brand_id}, page=page, page_size=page_size)


@router.get("/{decision_type}/{decision_id}")
async def get_decision(decision_type: str, decision_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    service = DECISION_SERVICES.get(decision_type)
    if service is None:
        raise HTTPException(status_code=400, detail=f"Unknown decision type: {decision_type}")
    try:
        return await service.get_or_404(db, decision_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Decision not found")
