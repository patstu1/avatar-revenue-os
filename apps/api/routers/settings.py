"""Settings, integrations, and secrets management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from apps.api.deps import AdminUser, DBSession
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Organization

router = APIRouter()
org_service = CRUDService(Organization)


class OrganizationSettingsUpdate(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    settings: Optional[dict] = None


class OrganizationSettingsResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    settings: Optional[dict]

    model_config = {"from_attributes": True}


class ProviderKeyStatus(BaseModel):
    provider: str
    configured: bool
    key_preview: str


class IntegrationsOverview(BaseModel):
    providers: list[ProviderKeyStatus]


@router.get("/organization", response_model=OrganizationSettingsResponse)
async def get_organization_settings(current_user: AdminUser, db: DBSession):
    try:
        return await org_service.get_or_404(db, current_user.organization_id)
    except ValueError:
        raise HTTPException(status_code=404)


@router.patch("/organization", response_model=OrganizationSettingsResponse)
async def update_organization_settings(
    body: OrganizationSettingsUpdate, current_user: AdminUser, db: DBSession
):
    try:
        org = await org_service.update(
            db, current_user.organization_id, **body.model_dump(exclude_unset=True)
        )
    except ValueError:
        raise HTTPException(status_code=404)
    await log_action(
        db, "organization.settings_updated",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="organization",
        entity_id=current_user.organization_id,
    )
    return org


@router.get("/integrations", response_model=IntegrationsOverview)
async def get_integrations(current_user: AdminUser, db: DBSession):
    from apps.api.config import get_settings
    s = get_settings()

    def mask(key: str) -> str:
        if not key:
            return ""
        if len(key) < 8:
            return "****"
        return key[:4] + "****" + key[-4:]

    providers = [
        ProviderKeyStatus(provider="openai", configured=bool(s.openai_api_key), key_preview=mask(s.openai_api_key)),
        ProviderKeyStatus(provider="elevenlabs", configured=bool(s.elevenlabs_api_key), key_preview=mask(s.elevenlabs_api_key)),
        ProviderKeyStatus(provider="tavus", configured=bool(s.tavus_api_key), key_preview=mask(s.tavus_api_key)),
        ProviderKeyStatus(provider="heygen", configured=bool(s.heygen_api_key), key_preview=mask(s.heygen_api_key)),
        ProviderKeyStatus(provider="s3", configured=bool(s.s3_access_key_id), key_preview=mask(s.s3_access_key_id)),
    ]
    return IntegrationsOverview(providers=providers)
