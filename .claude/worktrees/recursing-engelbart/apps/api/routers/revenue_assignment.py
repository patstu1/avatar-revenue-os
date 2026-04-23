"""Revenue assignment endpoints — link offers/affiliates/newsletters to brands."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.revenue_assignment import (
    RevenueAssignmentCreate,
    RevenueAssignmentResponse,
    RevenueAssignmentUpdate,
)
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Brand
from packages.db.models.revenue_assignment import RevenueAssignment

router = APIRouter()
ra_service = CRUDService(RevenueAssignment)
brand_service = CRUDService(Brand)


@router.post("/", response_model=RevenueAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_revenue_assignment(body: RevenueAssignmentCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    ra = await ra_service.create(db, **body.model_dump())
    await log_action(
        db, "revenue_assignment.created",
        organization_id=current_user.organization_id, brand_id=body.brand_id,
        user_id=current_user.id, actor_type="human",
        entity_type="revenue_assignment", entity_id=ra.id,
    )
    return ra


@router.get("/", response_model=list[RevenueAssignmentResponse])
async def list_revenue_assignments(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    assignment_type: str | None = None,
    page: int = Query(1, ge=1),
):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    filters: dict = {"brand_id": brand_id}
    if assignment_type:
        filters["assignment_type"] = assignment_type
    result = await ra_service.list(db, filters=filters, page=page)
    return result["items"]


@router.patch("/{assignment_id}", response_model=RevenueAssignmentResponse)
async def update_revenue_assignment(
    assignment_id: uuid.UUID, body: RevenueAssignmentUpdate, current_user: CurrentUser, db: DBSession,
):
    try:
        ra = await ra_service.get_or_404(db, assignment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Revenue assignment not found")
    brand = await brand_service.get(db, ra.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(ra, key, value)
    await db.flush()
    await db.refresh(ra)
    return ra


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_revenue_assignment(assignment_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        ra = await ra_service.get_or_404(db, assignment_id)
    except ValueError:
        raise HTTPException(status_code=404)
    brand = await brand_service.get(db, ra.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await ra_service.delete(db, assignment_id)
    await log_action(
        db, "revenue_assignment.deleted",
        organization_id=current_user.organization_id, user_id=current_user.id,
        actor_type="human", entity_type="revenue_assignment", entity_id=assignment_id,
    )
