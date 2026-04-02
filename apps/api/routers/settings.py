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


@router.get("/integrations")
async def get_integrations(current_user: AdminUser, db: DBSession):
    import os
    from apps.api.config import get_settings
    s = get_settings()

    def mask(key: str) -> str:
        if not key:
            return ""
        if len(key) < 8:
            return "****"
        return key[:4] + "****" + key[-4:]

    ALL_PROVIDERS = [
        ("anthropic", "Claude Sonnet — Hero text / orchestrator", s.anthropic_api_key),
        ("google_ai", "Gemini Flash + Imagen 4 + YouTube API", s.google_ai_api_key),
        ("deepseek", "DeepSeek — Bulk text / scanning", s.deepseek_api_key),
        ("openai", "GPT Image 1.5 — Hero images", s.openai_api_key),
        ("fal", "Kling video + Flux images (via fal.ai)", s.fal_api_key),
        ("runway", "Runway Gen-4 Turbo — Premium video", s.runway_api_key),
        ("higgsfield", "Higgsfield Cinema Studio — Cinematic video", os.environ.get("HIGGSFIELD_API_KEY", "")),
        ("heygen", "HeyGen — Hero avatar video", s.heygen_api_key),
        ("did", "D-ID — Standard avatar video", s.did_api_key),
        ("synthesia", "Synthesia — Bulk avatar video", os.environ.get("SYNTHESIA_API_KEY", "")),
        ("elevenlabs", "ElevenLabs — Hero voice / TTS", s.elevenlabs_api_key),
        ("fish_audio", "Fish Audio — Standard voice", s.fish_audio_api_key),
        ("mistral", "Voxtral — Bulk voice", s.mistral_api_key),
        ("suno", "Suno — Hero music", s.suno_api_key),
        ("mubert", "Mubert — Standard music", os.environ.get("MUBERT_API_KEY", "")),
        ("stability", "Stable Audio — Bulk music", os.environ.get("STABILITY_API_KEY", "")),
        ("buffer", "Buffer — Social publishing", os.environ.get("BUFFER_API_KEY", "")),
        ("publer", "Publer — Social publishing (failover)", os.environ.get("PUBLER_API_KEY", "")),
        ("ayrshare", "Ayrshare — Social publishing (failover)", os.environ.get("AYRSHARE_API_KEY", "")),
        ("stripe", "Stripe — Payment / revenue tracking", os.environ.get("STRIPE_API_KEY", "")),
        ("impact", "Impact — Affiliate network (Spotify, Target)", os.environ.get("IMPACT_ACCOUNT_SID", "")),
        ("shareasale", "ShareASale — Affiliate network", os.environ.get("SHAREASALE_API_TOKEN", "")),
        ("clickbank", "ClickBank — Digital product affiliates", os.environ.get("CLICKBANK_API_KEY", "")),
        ("amazon", "Amazon Associates — Retail affiliates", os.environ.get("AMAZON_ASSOCIATES_TAG", "")),
        ("semrush", "Semrush — $200/sale affiliate", os.environ.get("SEMRUSH_AFFILIATE_KEY", "")),
        ("tiktok_shop", "TikTok Shop — Product commerce", os.environ.get("TIKTOK_SHOP_ACCESS_TOKEN", "")),
        ("etsy", "Etsy — Marketplace affiliate", os.environ.get("ETSY_AFFILIATE_API_KEY", "")),
        ("s3", "S3 — Object storage (media)", s.s3_access_key_id),
        ("smtp", "SMTP — Email sending", os.environ.get("SMTP_HOST", "")),
        ("twilio", "Twilio — SMS", os.environ.get("TWILIO_ACCOUNT_SID", "")),
        ("sentry", "Sentry — Error monitoring", s.sentry_dsn),
    ]

    providers = [
        ProviderKeyStatus(provider=name, configured=bool(key), key_preview=mask(key))
        for name, desc, key in ALL_PROVIDERS
    ]
    return IntegrationsOverview(providers=providers, descriptions={name: desc for name, desc, _ in ALL_PROVIDERS})


class IntegrationsOverview(BaseModel):
    providers: list[ProviderKeyStatus]
    descriptions: dict[str, str] = {}
