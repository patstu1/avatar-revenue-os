"""Settings, integrations, and secrets management endpoints."""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.deps import AdminUser, DBSession
from apps.api.services import secrets_service
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Organization

router = APIRouter()
org_service = CRUDService(Organization)

# Maps settings/dashboard provider name → integration_providers.provider_key.
# When the dashboard saves a key under "anthropic", it also needs to write
# to integration_providers under "claude" (which is what the workers read).
# If the key is the same in both tables, it maps to itself.
SETTINGS_TO_IP_KEY = {
    "anthropic": "claude",
    "google_ai": "gemini_flash",
    "openai": "openai_image",
    "fal": "flux",
    "mistral": "voxtral",
    # Everything else maps to itself (buffer → buffer, stripe → stripe, etc.)
}


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
    source: str  # "dashboard", "provider_db", "none"
    health: Optional[str] = None  # "healthy", "configured", "auth_failed", "unconfigured", None


class SaveKeyRequest(BaseModel):
    api_key: str


class SaveKeyResponse(BaseModel):
    provider: str
    configured: bool
    key_preview: str


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


@router.put("/api-keys/{provider}", response_model=SaveKeyResponse)
async def save_api_key(
    provider: str, body: SaveKeyRequest, current_user: AdminUser, db: DBSession
):
    if provider not in secrets_service.ENV_KEY_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    key_value = body.api_key.strip()

    # Write to provider_secrets (dashboard display + backup)
    await secrets_service.save_key(
        db, current_user.organization_id, provider, key_value, current_user.id
    )

    # ALSO write to integration_providers (where workers actually read from).
    # This closes the split-truth gap: dashboard saves reach the workers.
    from apps.api.services.integration_manager import set_credential
    ip_key = SETTINGS_TO_IP_KEY.get(provider, provider)
    result = await set_credential(
        db, current_user.organization_id, ip_key,
        api_key=key_value,
    )
    if result.get("error"):
        # Provider doesn't exist in integration_providers yet — that's OK,
        # the provider_secrets save already succeeded. Worker-side will fall
        # back to the secrets table or skip gracefully.
        import structlog
        structlog.get_logger().warning("settings.ip_save_skipped",
                                       provider=provider, ip_key=ip_key,
                                       reason=result["error"])

    await log_action(
        db, "api_key.saved",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="provider_secret",
        details={"provider": provider},
    )
    return SaveKeyResponse(
        provider=provider,
        configured=True,
        key_preview=secrets_service.mask_key(key_value),
    )


@router.delete("/api-keys/{provider}", status_code=204)
async def delete_api_key(
    provider: str, current_user: AdminUser, db: DBSession
):
    if provider not in secrets_service.ENV_KEY_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    deleted = await secrets_service.delete_key(
        db, current_user.organization_id, provider
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="No key stored for this provider")

    await log_action(
        db, "api_key.deleted",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="provider_secret",
        details={"provider": provider},
    )


@router.get("/integrations")
async def get_integrations(current_user: AdminUser, db: DBSession):
    """List all providers with their configuration status.

    Truth priority: integration_providers (DB, worker-visible) > provider_secrets
    (dashboard saves) > env vars (server config). Health status comes from
    integration_providers since that's where workers check connectivity.
    """
    from sqlalchemy import select

    from apps.api.services.integration_manager import _decrypt
    from packages.db.models.integration_registry import IntegrationProvider

    # Load from all three sources
    db_secrets = await secrets_service.get_all_keys(db, current_user.organization_id)

    # Load integration_providers (worker truth)
    ip_rows = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == current_user.organization_id,
            IntegrationProvider.is_active.is_(True),
        )
    )).scalars().all()
    ip_map = {row.provider_key: row for row in ip_rows}

    ALL_PROVIDERS = [
        # --- Brain / Text AI ---
        ("anthropic", "Claude Sonnet — Hero text / orchestrator", "claude"),
        ("google_ai", "Gemini Flash + Imagen 4 + YouTube API", "gemini_flash"),
        ("deepseek", "DeepSeek — Bulk text / scanning", "deepseek"),
        ("openai", "GPT Image 1.5 — Hero images", "openai_image"),
        ("groq", "Groq — Bulk text (fast)", "groq"),
        ("xai", "xAI Grok", None),
        # --- Image ---
        ("fal", "Kling video + Flux images (via fal.ai)", "flux"),
        ("replicate", "Replicate — Image / video models", None),
        # --- Video ---
        ("runway", "Runway Gen-4 Turbo — Premium video", "runway"),
        ("kling", "Kling — Standard video", "kling"),
        # --- Avatar ---
        ("heygen", "HeyGen — Hero avatar video", "heygen"),
        ("did", "D-ID — Standard avatar video", "did"),
        ("tavus", "Tavus — Optional avatar", "tavus"),
        # --- Voice / Music ---
        ("elevenlabs", "ElevenLabs — Hero voice / TTS", "elevenlabs"),
        ("fish_audio", "Fish Audio — Standard voice", "fish_audio"),
        ("mistral", "Voxtral — Bulk voice", "voxtral"),
        ("suno", "Suno — Hero music", None),
        ("mubert", "Mubert — Standard music", None),
        # --- Publishing ---
        ("buffer", "Buffer — Social publishing", "buffer"),
        ("publer", "Publer — Social publishing (failover)", "publer"),
        ("ayrshare", "Ayrshare — Social publishing (failover)", "ayrshare"),
        # --- Analytics / Trends ---
        ("serpapi", "SerpAPI — Search trends", "serpapi"),
        ("youtube_analytics", "YouTube Analytics API", "youtube_analytics"),
        ("tiktok_analytics", "TikTok Analytics", "tiktok_analytics"),
        ("instagram_analytics", "Instagram Analytics", "instagram_analytics"),
        # --- Payments / Affiliates ---
        ("stripe", "Stripe — Payment / revenue tracking", "stripe"),
        ("clickbank", "ClickBank — Digital product affiliates", None),
        # --- Infrastructure ---
        ("smtp", "SMTP — Email sending", "smtp"),
        ("imap", "IMAP — Email inbox polling", "imap"),
        ("twilio", "Twilio — SMS", "twilio"),
    ]

    providers = []
    for settings_key, desc, ip_key in ALL_PROVIDERS:
        # Check integration_providers first (worker truth)
        ip_row = ip_map.get(ip_key) if ip_key else None
        has_ip_key = bool(ip_row and ip_row.api_key_encrypted and len(ip_row.api_key_encrypted) > 5)
        health = ip_row.health_status if ip_row else None

        # Then check provider_secrets (dashboard saves)
        dashboard_val = db_secrets.get(settings_key, "")

        # Determine source and resolved state
        if has_ip_key:
            try:
                resolved = _decrypt(ip_row.api_key_encrypted)
            except Exception:
                resolved = ""
            source = "dashboard" if dashboard_val else "provider_db"
        elif dashboard_val:
            resolved = dashboard_val
            source = "dashboard"
        else:
            resolved = ""
            source = "none"

        providers.append(
            ProviderKeyStatus(
                provider=settings_key,
                configured=bool(resolved),
                key_preview=secrets_service.mask_key(resolved),
                source=source,
                health=health,
            )
        )

    return IntegrationsOverview(
        providers=providers,
        descriptions={name: desc for name, desc, _ in ALL_PROVIDERS},
    )


class IntegrationsOverview(BaseModel):
    providers: list[ProviderKeyStatus]
    descriptions: dict[str, str] = {}
