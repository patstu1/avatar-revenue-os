"""Integrations Dashboard API — manage providers, credentials, accounts, connections."""
from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import integration_manager as im

router = APIRouter()


@router.post("/integrations/seed")
async def seed_providers(current_user: OperatorUser, db: DBSession):
    """Seed default provider catalog for this organization."""
    result = await im.seed_provider_catalog(db, current_user.organization_id)
    await db.commit()
    return result


@router.get("/integrations/providers")
async def list_providers(current_user: CurrentUser, db: DBSession,
                          category: str = Query(None)):
    """List all providers with status. Credentials are masked."""
    return await im.list_providers(db, current_user.organization_id, category)


@router.post("/integrations/providers/{provider_key}/credential")
async def set_credential(provider_key: str, current_user: OperatorUser, db: DBSession,
                          api_key: str = Query(None), api_secret: str = Query(None),
                          oauth_token: str = Query(None)):
    """Set or update credentials for a provider. Encrypted before storage."""
    result = await im.set_credential(db, current_user.organization_id, provider_key,
                                      api_key=api_key, api_secret=api_secret, oauth_token=oauth_token)
    if "error" in result:
        raise HTTPException(400, result["error"])
    await db.commit()
    return result


@router.get("/integrations/route")
async def get_provider_for_task(current_user: CurrentUser, db: DBSession,
                                 category: str = Query(...), quality_tier: str = Query("standard")):
    """Get the best available provider for a task. Used by content pipeline."""
    result = await im.get_provider_for_task(db, current_user.organization_id, category, quality_tier)
    if not result:
        return {"error": f"No configured provider for {category}/{quality_tier}"}
    # Mask API key in response
    if result.get("api_key"):
        result["api_key_preview"] = result["api_key"][:8] + "..." if len(result["api_key"]) > 8 else "***"
        del result["api_key"]
    return result


@router.post("/integrations/providers/{provider_key}/enable")
async def enable_provider(provider_key: str, current_user: OperatorUser, db: DBSession):
    """Enable a provider."""
    from sqlalchemy import select, update
    from packages.db.models.integration_registry import IntegrationProvider
    await db.execute(update(IntegrationProvider).where(
        IntegrationProvider.organization_id == current_user.organization_id,
        IntegrationProvider.provider_key == provider_key,
    ).values(is_enabled=True))
    await db.commit()
    return {"provider": provider_key, "enabled": True}


@router.post("/integrations/providers/{provider_key}/disable")
async def disable_provider(provider_key: str, current_user: OperatorUser, db: DBSession):
    """Disable a provider."""
    from sqlalchemy import update
    from packages.db.models.integration_registry import IntegrationProvider
    await db.execute(update(IntegrationProvider).where(
        IntegrationProvider.organization_id == current_user.organization_id,
        IntegrationProvider.provider_key == provider_key,
    ).values(is_enabled=False))
    await db.commit()
    return {"provider": provider_key, "enabled": False}
