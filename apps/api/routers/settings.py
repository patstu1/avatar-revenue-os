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
    source: str


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

    await secrets_service.save_key(
        db, current_user.organization_id, provider, body.api_key.strip(), current_user.id
    )
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
        key_preview=secrets_service.mask_key(body.api_key.strip()),
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
    import os
    from apps.api.config import get_settings
    s = get_settings()

    db_keys = await secrets_service.get_all_keys(db, current_user.organization_id)

    ALL_PROVIDERS = [
        # --- Brain / Text AI ---
        ("anthropic", "Claude Sonnet — Hero text / orchestrator", s.anthropic_api_key),
        ("google_ai", "Gemini Flash + Imagen 4 + YouTube API", s.google_ai_api_key),
        ("deepseek", "DeepSeek — Bulk text / scanning", s.deepseek_api_key),
        ("openai", "GPT Image 1.5 — Hero images", s.openai_api_key),
        ("groq", "Groq — Bulk text (fast)", s.groq_api_key),
        ("xai", "xAI Grok", s.xai_api_key),
        # --- Image ---
        ("fal", "Kling video + Flux images (via fal.ai)", s.fal_api_key),
        ("replicate", "Replicate — Image / video models", s.replicate_api_token),
        ("higgsfield", "Higgsfield Cinema Studio — Cinematic video", os.environ.get("HIGGSFIELD_API_KEY", "")),
        ("stability", "Stable Diffusion / Audio", os.environ.get("STABILITY_API_KEY", "")),
        # --- Video ---
        ("runway", "Runway Gen-4 Turbo — Premium video", s.runway_api_key),
        ("kling", "Kling — Standard video", s.kling_api_key),
        # --- Avatar ---
        ("heygen", "HeyGen — Hero avatar video", s.heygen_api_key),
        ("did", "D-ID — Standard avatar video", s.did_api_key),
        ("tavus", "Tavus — Optional avatar", s.tavus_api_key),
        ("synthesia", "Synthesia — Bulk avatar video", os.environ.get("SYNTHESIA_API_KEY", "")),
        # --- Voice / Music ---
        ("elevenlabs", "ElevenLabs — Hero voice / TTS", s.elevenlabs_api_key),
        ("fish_audio", "Fish Audio — Standard voice", s.fish_audio_api_key),
        ("mistral", "Voxtral — Bulk voice", s.mistral_api_key),
        ("suno", "Suno — Hero music", s.suno_api_key),
        ("mubert", "Mubert — Standard music", s.mubert_api_key),
        # --- Publishing ---
        ("buffer", "Buffer — Social publishing", s.buffer_api_key),
        ("publer", "Publer — Social publishing (failover)", s.publer_api_key),
        ("ayrshare", "Ayrshare — Social publishing (failover)", s.ayrshare_api_key),
        # --- Analytics / Trends ---
        ("serpapi", "SerpAPI — Search trends", s.serpapi_key),
        ("youtube_analytics", "YouTube Analytics API", s.youtube_api_key),
        ("tiktok_analytics", "TikTok Analytics", s.tiktok_access_token),
        ("instagram_analytics", "Instagram Analytics", s.instagram_access_token),
        # --- Payments / Affiliates ---
        ("stripe", "Stripe — Payment / revenue tracking", s.stripe_api_key),
        ("clickbank", "ClickBank — Digital product affiliates", s.clickbank_api_key),
        ("impact", "Impact — Affiliate network (Spotify, Target)", os.environ.get("IMPACT_ACCOUNT_SID", "")),
        ("shareasale", "ShareASale — Affiliate network", os.environ.get("SHAREASALE_API_TOKEN", "")),
        ("amazon", "Amazon Associates — Retail affiliates", os.environ.get("AMAZON_ASSOCIATES_TAG", "")),
        ("semrush", "Semrush — $200/sale affiliate", os.environ.get("SEMRUSH_AFFILIATE_KEY", "")),
        ("tiktok_shop", "TikTok Shop — Product commerce", os.environ.get("TIKTOK_SHOP_ACCESS_TOKEN", "")),
        ("etsy", "Etsy — Marketplace affiliate", os.environ.get("ETSY_AFFILIATE_API_KEY", "")),
        # --- Infrastructure ---
        ("s3", "S3 — Object storage (media)", s.s3_access_key_id),
        ("smtp", "SMTP — Email sending", s.smtp_host),
        ("imap", "IMAP — Email inbox polling", s.imap_host),
        ("twilio", "Twilio — SMS", os.environ.get("TWILIO_ACCOUNT_SID", "")),
        ("sentry", "Sentry — Error monitoring", s.sentry_dsn),
    ]

    providers = []
    for name, desc, env_val in ALL_PROVIDERS:
        db_val = db_keys.get(name, "")
        resolved = db_val or env_val
        source = "dashboard" if db_val else ("server" if env_val else "none")
        providers.append(
            ProviderKeyStatus(
                provider=name,
                configured=bool(resolved),
                key_preview=secrets_service.mask_key(resolved),
                source=source,
            )
        )

    return IntegrationsOverview(
        providers=providers,
        descriptions={name: desc for name, desc, _ in ALL_PROVIDERS},
    )


class IntegrationsOverview(BaseModel):
    providers: list[ProviderKeyStatus]
    descriptions: dict[str, str] = {}
