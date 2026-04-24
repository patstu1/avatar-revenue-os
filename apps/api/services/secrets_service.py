"""Service for encrypted provider API key storage and retrieval."""

import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from packages.db.models.provider_secrets import ProviderSecret

ENV_KEY_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "google_ai": "GOOGLE_AI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "fal": "FAL_API_KEY",
    "runway": "RUNWAY_API_KEY",
    "higgsfield": "HIGGSFIELD_API_KEY",
    "heygen": "HEYGEN_API_KEY",
    "did": "DID_API_KEY",
    "synthesia": "SYNTHESIA_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
    "fish_audio": "FISH_AUDIO_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "suno": "SUNO_API_KEY",
    "mubert": "MUBERT_API_KEY",
    "stability": "STABILITY_API_KEY",
    "tavus": "TAVUS_API_KEY",
    "buffer": "BUFFER_API_KEY",
    "publer": "PUBLER_API_KEY",
    "ayrshare": "AYRSHARE_API_KEY",
    "stripe": "STRIPE_API_KEY",
    "impact": "IMPACT_ACCOUNT_SID",
    "shareasale": "SHAREASALE_API_TOKEN",
    "clickbank": "CLICKBANK_API_KEY",
    "amazon": "AMAZON_ASSOCIATES_TAG",
    "semrush": "SEMRUSH_AFFILIATE_KEY",
    "tiktok_shop": "TIKTOK_SHOP_ACCESS_TOKEN",
    "etsy": "ETSY_AFFILIATE_API_KEY",
    "groq": "GROQ_API_KEY",
    "xai": "XAI_API_KEY",
    "replicate": "REPLICATE_API_TOKEN",
    "kling": "KLING_API_KEY",
    "serpapi": "SERPAPI_KEY",
    "youtube_analytics": "YOUTUBE_API_KEY",
    "tiktok_analytics": "TIKTOK_ACCESS_TOKEN",
    "instagram_analytics": "INSTAGRAM_ACCESS_TOKEN",
    "imap": "IMAP_HOST",
    "s3": "S3_ACCESS_KEY_ID",
    "smtp": "SMTP_HOST",
    "twilio": "TWILIO_ACCOUNT_SID",
    "sentry": "SENTRY_DSN",
}


def _get_fernet() -> Fernet:
    secret = get_settings().api_secret_key
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_value(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) < 8:
        return "****"
    return key[:4] + "****" + key[-4:]


async def save_key(
    db: AsyncSession,
    organization_id: uuid.UUID,
    provider_name: str,
    api_key: str,
    user_id: Optional[uuid.UUID] = None,
) -> ProviderSecret:
    encrypted = encrypt_value(api_key)
    now = datetime.now(timezone.utc)

    stmt = select(ProviderSecret).where(
        ProviderSecret.organization_id == organization_id,
        ProviderSecret.provider_name == provider_name,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_value = encrypted
        existing.updated_by = user_id
        existing.last_rotated_at = now
        await db.flush()
        return existing

    secret = ProviderSecret(
        organization_id=organization_id,
        provider_name=provider_name,
        encrypted_value=encrypted,
        updated_by=user_id,
        last_rotated_at=now,
    )
    db.add(secret)
    await db.flush()
    return secret


async def get_key(db: AsyncSession, organization_id: uuid.UUID, provider_name: str) -> Optional[str]:
    stmt = select(ProviderSecret).where(
        ProviderSecret.organization_id == organization_id,
        ProviderSecret.provider_name == provider_name,
    )
    result = await db.execute(stmt)
    secret = result.scalar_one_or_none()
    if secret:
        return decrypt_value(secret.encrypted_value)
    return None


async def delete_key(db: AsyncSession, organization_id: uuid.UUID, provider_name: str) -> bool:
    stmt = delete(ProviderSecret).where(
        ProviderSecret.organization_id == organization_id,
        ProviderSecret.provider_name == provider_name,
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def get_all_keys(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, str]:
    stmt = select(ProviderSecret).where(ProviderSecret.organization_id == organization_id)
    result = await db.execute(stmt)
    secrets = result.scalars().all()
    return {s.provider_name: decrypt_value(s.encrypted_value) for s in secrets}


def resolve_key(provider_name: str, db_keys: dict[str, str]) -> str:
    """Check DB-stored key first, then fall back to env var."""
    db_val = db_keys.get(provider_name, "")
    if db_val:
        return db_val
    env_name = ENV_KEY_MAP.get(provider_name, "")
    if env_name:
        return os.environ.get(env_name, "")
    return ""
