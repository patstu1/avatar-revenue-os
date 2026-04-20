"""Settings, integrations, and secrets management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from apps.api.deps import AdminUser, DBSession
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from apps.api.services import secrets_service
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
    from packages.db.models.integration_registry import IntegrationProvider
    from apps.api.services.integration_manager import _decrypt

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


# ═════════════════════════════════════════════════════════════════════════
# Multi-field provider upsert — PUT /settings/providers/{provider_key}
# ═════════════════════════════════════════════════════════════════════════
#
# Covers credentials that need more than a single api_key: SMTP (host/port/
# username/password/from_email/use_tls), inbound-email routing rows, webhook
# signing secrets (stripe_webhook / shopify_webhook), and any future multi-
# field provider. Writes directly into `integration_providers` using the
# same Fernet encryption + extra_config layout that Phase 3's `SmtpEmailClient.
# resolve` and `_resolve_inbound_org_id` already read from.
#
# Env is deliberately NOT consulted by this endpoint — the point of the
# endpoint is to be the system-owned primary path for putting credentials
# INTO the DB. The env-legacy read paths remain elsewhere, loudly logged.
#
# This endpoint is AdminUser-only. Operators cannot write credentials.


# Well-known multi-field provider keys — used for (a) sensible defaults on
# first-time creation of the integration_providers row, and (b) a tiny
# allowlist of extra_config fields surfaced back in the response so the UI
# knows what it can safely display without leaking secrets.
PROVIDER_DEFAULTS: dict[str, dict] = {
    "smtp": {
        "provider_name": "SMTP Email (system-managed)",
        "provider_category": "email",
        "public_extra_fields": ["host", "port", "username", "from_email", "use_tls"],
    },
    "inbound_email_route": {
        "provider_name": "Inbound Email Route",
        "provider_category": "inbox",
        "public_extra_fields": ["to_address", "to_domain", "plus_token"],
    },
    "stripe_webhook": {
        "provider_name": "Stripe Webhook Signing Secret",
        "provider_category": "payment",
        "public_extra_fields": [],
    },
    "shopify_webhook": {
        "provider_name": "Shopify Webhook Signing Secret",
        "provider_category": "payment",
        "public_extra_fields": [],
    },
    "stripe": {
        "provider_name": "Stripe",
        "provider_category": "payment",
        "public_extra_fields": ["publishable_key", "account_id", "webhook_endpoint"],
    },
}


class UpsertProviderRequest(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    oauth_token: Optional[str] = None
    extra_config: Optional[dict] = None
    is_enabled: Optional[bool] = None
    provider_name: Optional[str] = None      # used only on CREATE
    provider_category: Optional[str] = None  # used only on CREATE


class ProviderUpsertResponse(BaseModel):
    provider_key: str
    created: bool                # True if the row was created by this call
    is_enabled: bool
    health_status: str
    has_api_key: bool
    has_api_secret: bool
    has_oauth_token: bool
    extra_config_public: dict    # only the non-secret fields
    key_preview: str             # masked


@router.put("/providers/{provider_key}", response_model=ProviderUpsertResponse)
async def upsert_provider(
    provider_key: str,
    body: UpsertProviderRequest,
    current_user: AdminUser,
    db: DBSession,
):
    """Create or update an ``integration_providers`` row for the caller's org.

    Upsert semantics:
      - If no row exists for (org_id, provider_key), create one using
        ``provider_name`` / ``provider_category`` from the request, or from
        PROVIDER_DEFAULTS, or a generic fallback.
      - If a row exists, update only the fields present in the request.
        ``extra_config`` is merged shallow-right (request overrides DB keys).

    Secrets (``api_key``, ``api_secret``, ``oauth_token``) are Fernet-encrypted
    at write time via ``integration_manager._encrypt``.

    Env vars are never consulted. The response masks secrets and only returns
    the ``public_extra_fields`` declared in PROVIDER_DEFAULTS (or an empty
    dict for unknown providers), so no secrets ever leak back to the client.
    """
    from sqlalchemy import select
    from apps.api.services.integration_manager import _encrypt
    from packages.db.models.integration_registry import IntegrationProvider

    provider_key = (provider_key or "").strip()
    if not provider_key:
        raise HTTPException(status_code=400, detail="provider_key required")

    row = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == current_user.organization_id,
            IntegrationProvider.provider_key == provider_key,
        )
    )).scalar_one_or_none()

    defaults = PROVIDER_DEFAULTS.get(provider_key, {})

    created = False
    if row is None:
        row = IntegrationProvider(
            organization_id=current_user.organization_id,
            provider_key=provider_key,
            provider_name=body.provider_name or defaults.get("provider_name", provider_key),
            provider_category=body.provider_category or defaults.get("provider_category", "generic"),
            is_enabled=True if body.is_enabled is None else body.is_enabled,
            health_status="unconfigured",
            priority_order=10,
            quality_tier="standard",
            cost_per_unit=0.0,
        )
        db.add(row)
        created = True

    if body.api_key is not None:
        row.api_key_encrypted = _encrypt(body.api_key) if body.api_key else None
    if body.api_secret is not None:
        row.api_secret_encrypted = _encrypt(body.api_secret) if body.api_secret else None
    if body.oauth_token is not None:
        row.oauth_token_encrypted = _encrypt(body.oauth_token) if body.oauth_token else None
    if body.extra_config is not None:
        merged = dict(row.extra_config or {})
        merged.update(body.extra_config)
        row.extra_config = merged
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled

    if row.api_key_encrypted or row.oauth_token_encrypted or row.extra_config:
        row.health_status = "configured"

    await db.flush()

    await log_action(
        db,
        "integration_provider.upserted",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="integration_provider",
        entity_id=row.id,
        details={
            "provider_key": provider_key,
            "created": created,
            "fields_changed": [
                k for k, present in (
                    ("api_key", body.api_key is not None),
                    ("api_secret", body.api_secret is not None),
                    ("oauth_token", body.oauth_token is not None),
                    ("extra_config", body.extra_config is not None),
                    ("is_enabled", body.is_enabled is not None),
                ) if present
            ],
        },
    )

    # Filter extra_config to the public field allowlist for this provider.
    allowed_public = set(defaults.get("public_extra_fields", []))
    ec = row.extra_config or {}
    if allowed_public:
        public_ec = {k: v for k, v in ec.items() if k in allowed_public}
    else:
        public_ec = {}

    return ProviderUpsertResponse(
        provider_key=provider_key,
        created=created,
        is_enabled=row.is_enabled,
        health_status=row.health_status,
        has_api_key=bool(row.api_key_encrypted),
        has_api_secret=bool(row.api_secret_encrypted),
        has_oauth_token=bool(row.oauth_token_encrypted),
        extra_config_public=public_ec,
        key_preview=secrets_service.mask_key("*" * 12) if row.api_key_encrypted else "",
    )


@router.get("/providers/{provider_key}", response_model=ProviderUpsertResponse)
async def get_provider(
    provider_key: str,
    current_user: AdminUser,
    db: DBSession,
):
    """Read current state of a provider row. Never returns decrypted secrets."""
    from sqlalchemy import select
    from packages.db.models.integration_registry import IntegrationProvider

    row = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == current_user.organization_id,
            IntegrationProvider.provider_key == provider_key,
        )
    )).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_key}' not configured")

    defaults = PROVIDER_DEFAULTS.get(provider_key, {})
    allowed_public = set(defaults.get("public_extra_fields", []))
    ec = row.extra_config or {}
    public_ec = {k: v for k, v in ec.items() if k in allowed_public} if allowed_public else {}

    return ProviderUpsertResponse(
        provider_key=provider_key,
        created=False,
        is_enabled=row.is_enabled,
        health_status=row.health_status,
        has_api_key=bool(row.api_key_encrypted),
        has_api_secret=bool(row.api_secret_encrypted),
        has_oauth_token=bool(row.oauth_token_encrypted),
        extra_config_public=public_ec,
        key_preview=secrets_service.mask_key("*" * 12) if row.api_key_encrypted else "",
    )


@router.delete("/providers/{provider_key}", status_code=204)
async def delete_provider(
    provider_key: str,
    current_user: AdminUser,
    db: DBSession,
):
    """Delete a provider row. Used to reset / rotate out a credential entirely."""
    from sqlalchemy import select
    from packages.db.models.integration_registry import IntegrationProvider

    row = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == current_user.organization_id,
            IntegrationProvider.provider_key == provider_key,
        )
    )).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_key}' not configured")

    await db.delete(row)
    await log_action(
        db,
        "integration_provider.deleted",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="integration_provider",
        entity_id=row.id,
        details={"provider_key": provider_key},
    )
