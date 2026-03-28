"""Organization management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.core import OrganizationResponse
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Organization

router = APIRouter()
org_service = CRUDService(Organization)


@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(current_user: CurrentUser, db: DBSession):
    result = await org_service.list(db, filters={"id": current_user.organization_id})
    return result["items"]


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        return await org_service.get_or_404(db, org_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Organization not found")


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: uuid.UUID, current_user: CurrentUser, db: DBSession, name: str | None = None
):
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    try:
        org = await org_service.update(db, org_id, name=name)
    except ValueError:
        raise HTTPException(status_code=404, detail="Organization not found")
    await log_action(db, "organization.updated", organization_id=org_id, user_id=current_user.id, actor_type="human", entity_type="organization", entity_id=org_id)
    return org
