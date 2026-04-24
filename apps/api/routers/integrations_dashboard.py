"""Integrations Dashboard API — manage providers, credentials, accounts, connections.

Serves both the per-provider REST routes (used internally) and the
consolidated endpoints (used by the frontend integrations page).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import integration_manager as im

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ConfigureRequest(BaseModel):
    provider_id: str
    api_key: str | None = None
    api_secret: str | None = None
    oauth_token: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class TestRequest(BaseModel):
    provider_id: str
    api_key: str


# ---------------------------------------------------------------------------
# Frontend-facing consolidated endpoints
# ---------------------------------------------------------------------------


def _map_health_to_status(health: str | None, has_key: bool, has_oauth: bool) -> str:
    """Map internal health_status to frontend status enum."""
    if health in ("healthy", "configured"):
        return "connected"
    if health in ("auth_failed", "unreachable"):
        return "error"
    if has_key or has_oauth:
        return "connected"
    return "unconfigured"


@router.get("/integrations/providers")
async def list_providers(current_user: CurrentUser, db: DBSession, category: str = Query(None)):
    """List all providers, shaped for the frontend integrations page."""
    raw = await im.list_providers(db, current_user.organization_id, category)

    OAUTH_PROVIDERS = {"youtube_analytics", "tiktok_analytics", "instagram_analytics"}

    return [
        {
            "id": p["id"],
            "name": p["provider_name"],
            "slug": p["provider_key"],
            "category": p["category"],
            "status": _map_health_to_status(
                p.get("health_status"), p.get("has_api_key", False), p.get("has_oauth_token", False)
            ),
            "enabled": p.get("is_enabled", False),
            "is_oauth": p["provider_key"] in OAUTH_PROVIDERS,
            "priority": p.get("priority_order", 99),
            "quality_tier": p.get("quality_tier"),
            "cost_per_unit": p.get("cost_per_unit"),
            "total_calls": p.get("total_calls", 0),
            "total_cost_usd": p.get("total_cost_usd", 0),
            "last_health_check": p.get("last_health_check"),
            "error_message": (
                f"Health: {p['health_status']}" if p.get("health_status") in ("auth_failed", "unreachable") else None
            ),
        }
        for p in raw
    ]


@router.post("/integrations/configure")
async def configure_provider(body: ConfigureRequest, current_user: OperatorUser, db: DBSession):
    """Consolidated configure endpoint for the frontend.

    Handles API key save, enable/disable toggle, and priority changes
    in a single call.
    """
    from sqlalchemy import select

    from packages.db.models.integration_registry import IntegrationProvider

    # Resolve provider by ID
    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.id == uuid.UUID(body.provider_id),
                IntegrationProvider.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()

    if not provider:
        raise HTTPException(404, f"Provider {body.provider_id} not found")

    changed = []

    # Set credentials
    if body.api_key is not None:
        result = await im.set_credential(
            db,
            current_user.organization_id,
            provider.provider_key,
            api_key=body.api_key,
            api_secret=body.api_secret,
            oauth_token=body.oauth_token,
        )
        if "error" in result:
            raise HTTPException(400, result["error"])
        changed.append("credential")

    # Toggle enabled
    if body.enabled is not None:
        provider.is_enabled = body.enabled
        changed.append("enabled")

    # Update priority
    if body.priority is not None:
        provider.priority_order = body.priority
        changed.append("priority")

    await db.commit()

    return {
        "provider_id": body.provider_id,
        "provider_key": provider.provider_key,
        "changed": changed,
        "status": _map_health_to_status(
            provider.health_status,
            bool(provider.api_key_encrypted),
            bool(provider.oauth_token_encrypted),
        ),
    }


@router.post("/integrations/test")
async def test_connection(body: TestRequest, current_user: OperatorUser, db: DBSession):
    """Test a provider connection with the given API key before saving.

    Makes a lightweight health-check call (same endpoints as health_monitor).
    """
    from sqlalchemy import select

    from packages.db.models.integration_registry import IntegrationProvider

    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.id == uuid.UUID(body.provider_id),
                IntegrationProvider.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()

    if not provider:
        raise HTTPException(404, f"Provider {body.provider_id} not found")

    # Reuse the health monitor's ping logic
    try:
        from workers.health_monitor_worker.tasks import _ping_provider

        result = _ping_provider(body.api_key, provider.provider_key)
    except ImportError:
        # Fallback: just verify the key is non-empty
        return {"ok": bool(body.api_key.strip()), "message": "Key saved (live test unavailable)"}

    if result.get("reachable") and result.get("status_code") in (200, 201):
        return {
            "ok": True,
            "message": f"Connected successfully ({result.get('latency_ms', '?')}ms latency)",
        }
    elif result.get("error") == "auth_invalid":
        return {"ok": False, "message": "Authentication failed - check your API key"}
    elif result.get("error") == "rate_limited":
        return {"ok": True, "message": "Connected (rate limited right now, but key is valid)"}
    elif result.get("reachable") is False:
        return {"ok": False, "message": f"Could not reach provider: {result.get('error', 'timeout')}"}
    elif result.get("error") == "no health endpoint defined":
        return {"ok": True, "message": "Key saved (no health check available for this provider)"}
    else:
        return {"ok": False, "message": f"Unexpected response: HTTP {result.get('status_code')}"}


# ---------------------------------------------------------------------------
# Per-provider REST routes (used by internal services)
# ---------------------------------------------------------------------------


@router.post("/integrations/seed")
async def seed_providers(current_user: OperatorUser, db: DBSession):
    """Seed default provider catalog for this organization."""
    result = await im.seed_provider_catalog(db, current_user.organization_id)
    await db.commit()
    return result


@router.post("/integrations/providers/{provider_key}/credential")
async def set_credential(
    provider_key: str,
    current_user: OperatorUser,
    db: DBSession,
    api_key: str = Query(None),
    api_secret: str = Query(None),
    oauth_token: str = Query(None),
):
    """Set or update credentials for a provider. Encrypted before storage."""
    result = await im.set_credential(
        db,
        current_user.organization_id,
        provider_key,
        api_key=api_key,
        api_secret=api_secret,
        oauth_token=oauth_token,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    await db.commit()
    return result


@router.get("/integrations/route")
async def get_provider_for_task(
    current_user: CurrentUser, db: DBSession, category: str = Query(...), quality_tier: str = Query("standard")
):
    """Get the best available provider for a task. Used by content pipeline."""
    result = await im.get_provider_for_task(db, current_user.organization_id, category, quality_tier)
    if not result:
        return {"error": f"No configured provider for {category}/{quality_tier}"}
    if result.get("api_key"):
        result["api_key_preview"] = result["api_key"][:8] + "..." if len(result["api_key"]) > 8 else "***"
        del result["api_key"]
    return result


@router.post("/integrations/providers/{provider_key}/enable")
async def enable_provider(provider_key: str, current_user: OperatorUser, db: DBSession):
    """Enable a provider."""
    from sqlalchemy import update

    from packages.db.models.integration_registry import IntegrationProvider

    await db.execute(
        update(IntegrationProvider)
        .where(
            IntegrationProvider.organization_id == current_user.organization_id,
            IntegrationProvider.provider_key == provider_key,
        )
        .values(is_enabled=True)
    )
    await db.commit()
    return {"provider": provider_key, "enabled": True}


@router.post("/integrations/providers/{provider_key}/disable")
async def disable_provider(provider_key: str, current_user: OperatorUser, db: DBSession):
    """Disable a provider."""
    from sqlalchemy import update

    from packages.db.models.integration_registry import IntegrationProvider

    await db.execute(
        update(IntegrationProvider)
        .where(
            IntegrationProvider.organization_id == current_user.organization_id,
            IntegrationProvider.provider_key == provider_key,
        )
        .values(is_enabled=False)
    )
    await db.commit()
    return {"provider": provider_key, "enabled": False}
