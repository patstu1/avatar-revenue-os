"""Integration Manager — CRUD + health + credential management for providers.

This replaces .env-first credential management. Credentials are stored
encrypted in the integration_providers table and loaded at runtime.
"""
from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.integration_registry import IntegrationProvider, CreatorPlatformAccount

logger = structlog.get_logger()

# Simple encryption using Fernet-compatible approach with API_SECRET_KEY
def _get_cipher_key() -> bytes:
    secret = os.getenv("API_SECRET_KEY", "default-dev-key-not-for-production")
    return hashlib.sha256(secret.encode()).digest()


def _encrypt(value: str) -> str:
    """Encrypt a credential value. Uses XOR with hashed key for simplicity.
    For production: replace with Fernet or AWS KMS."""
    if not value:
        return ""
    key = _get_cipher_key()
    encrypted = bytes(a ^ b for a, b in zip(value.encode(), (key * ((len(value) // len(key)) + 1))[:len(value)]))
    return base64.b64encode(encrypted).decode()


def _decrypt(encrypted: str) -> str:
    """Decrypt a credential value."""
    if not encrypted:
        return ""
    key = _get_cipher_key()
    data = base64.b64decode(encrypted.encode())
    decrypted = bytes(a ^ b for a, b in zip(data, (key * ((len(data) // len(key)) + 1))[:len(data)]))
    return decrypted.decode()


# Default provider catalog
DEFAULT_PROVIDERS = [
    # LLM
    {"key": "claude", "name": "Claude Sonnet 4.6", "category": "llm", "tier": "hero", "cost": 0.003, "priority": 1},
    {"key": "gemini_flash", "name": "Gemini 2.5 Flash", "category": "llm", "tier": "standard", "cost": 0.0003, "priority": 5},
    {"key": "deepseek", "name": "DeepSeek V3.2", "category": "llm", "tier": "bulk", "cost": 0.00028, "priority": 10},
    {"key": "groq", "name": "Groq", "category": "llm", "tier": "bulk", "cost": 0.0001, "priority": 8},
    # Image
    {"key": "openai_image", "name": "GPT Image 1.5", "category": "image", "tier": "hero", "cost": 0.04, "priority": 1},
    {"key": "imagen4", "name": "Google Imagen 4 Fast", "category": "image", "tier": "standard", "cost": 0.02, "priority": 5},
    {"key": "flux", "name": "Flux 2 Pro (via fal.ai)", "category": "image", "tier": "standard", "cost": 0.055, "priority": 8},
    # Video
    {"key": "kling", "name": "Kling AI (via fal.ai)", "category": "video", "tier": "standard", "cost": 0.07, "priority": 5},
    {"key": "runway", "name": "Runway Gen-4 Turbo", "category": "video", "tier": "hero", "cost": 0.10, "priority": 1},
    # Avatar
    {"key": "heygen", "name": "HeyGen", "category": "avatar", "tier": "hero", "cost": 0.033, "priority": 1},
    {"key": "did", "name": "D-ID", "category": "avatar", "tier": "standard", "cost": 0.02, "priority": 5},
    # Voice
    {"key": "elevenlabs", "name": "ElevenLabs", "category": "voice", "tier": "hero", "cost": 0.0003, "priority": 1},
    {"key": "fish_audio", "name": "Fish Audio", "category": "voice", "tier": "standard", "cost": 0.000015, "priority": 5},
    {"key": "voxtral", "name": "Voxtral TTS (Mistral)", "category": "voice", "tier": "bulk", "cost": 0.000016, "priority": 10},
    # Publishing
    {"key": "buffer", "name": "Buffer", "category": "publishing", "tier": "standard", "cost": 0, "priority": 1},
    {"key": "publer", "name": "Publer", "category": "publishing", "tier": "standard", "cost": 0, "priority": 5},
    {"key": "ayrshare", "name": "Ayrshare", "category": "publishing", "tier": "standard", "cost": 0, "priority": 10},
    # Analytics
    {"key": "youtube_analytics", "name": "YouTube Analytics", "category": "analytics", "tier": "standard", "cost": 0, "priority": 1},
    {"key": "tiktok_analytics", "name": "TikTok Analytics", "category": "analytics", "tier": "standard", "cost": 0, "priority": 1},
    {"key": "instagram_analytics", "name": "Instagram Graph API", "category": "analytics", "tier": "standard", "cost": 0, "priority": 1},
    # Trends
    {"key": "serpapi", "name": "SerpAPI (Google Trends)", "category": "trends", "tier": "standard", "cost": 0.005, "priority": 1},
    # Email
    {"key": "smtp", "name": "SMTP Email", "category": "email", "tier": "standard", "cost": 0, "priority": 1},
    {"key": "imap", "name": "IMAP Inbox", "category": "inbox", "tier": "standard", "cost": 0, "priority": 1},
    # Payment
    {"key": "stripe", "name": "Stripe", "category": "payment", "tier": "standard", "cost": 0.029, "priority": 1},
]


async def seed_provider_catalog(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Seed the default provider catalog for an organization."""
    created = 0
    for p in DEFAULT_PROVIDERS:
        existing = (await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == org_id,
                IntegrationProvider.provider_key == p["key"],
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(IntegrationProvider(
                organization_id=org_id,
                provider_key=p["key"],
                provider_name=p["name"],
                provider_category=p["category"],
                quality_tier=p["tier"],
                cost_per_unit=p["cost"],
                priority_order=p["priority"],
                health_status="unconfigured",
            ))
            created += 1
    await db.flush()
    return {"created": created, "total_catalog": len(DEFAULT_PROVIDERS)}


async def set_credential(
    db: AsyncSession, org_id: uuid.UUID, provider_key: str,
    *, api_key: Optional[str] = None, api_secret: Optional[str] = None,
    oauth_token: Optional[str] = None, extra_config: Optional[dict] = None,
) -> dict:
    """Set or update credentials for a provider. Encrypts before storage."""
    provider = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_key == provider_key,
        )
    )).scalar_one_or_none()

    if not provider:
        return {"error": f"Provider '{provider_key}' not found. Run seed_provider_catalog first."}

    if api_key is not None:
        provider.api_key_encrypted = _encrypt(api_key)
    if api_secret is not None:
        provider.api_secret_encrypted = _encrypt(api_secret)
    if oauth_token is not None:
        provider.oauth_token_encrypted = _encrypt(oauth_token)
    if extra_config is not None:
        provider.extra_config = {**(provider.extra_config or {}), **extra_config}

    provider.health_status = "configured"
    provider.is_enabled = True
    await db.flush()

    return {"provider": provider_key, "status": "configured", "encrypted": True}


async def get_credential(db: AsyncSession, org_id: uuid.UUID, provider_key: str) -> Optional[str]:
    """Get decrypted API key for a provider. Used by services at runtime."""
    provider = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_key == provider_key,
            IntegrationProvider.is_enabled.is_(True),
        )
    )).scalar_one_or_none()

    if not provider or not provider.api_key_encrypted:
        return None
    return _decrypt(provider.api_key_encrypted)


async def list_providers(db: AsyncSession, org_id: uuid.UUID, category: Optional[str] = None) -> list[dict]:
    """List all providers with status (credentials masked)."""
    query = select(IntegrationProvider).where(IntegrationProvider.organization_id == org_id)
    if category:
        query = query.where(IntegrationProvider.provider_category == category)
    query = query.order_by(IntegrationProvider.provider_category, IntegrationProvider.priority_order)

    providers = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(p.id),
            "provider_key": p.provider_key,
            "provider_name": p.provider_name,
            "category": p.provider_category,
            "quality_tier": p.quality_tier,
            "priority_order": p.priority_order,
            "is_enabled": p.is_enabled,
            "is_primary": p.is_primary,
            "health_status": p.health_status,
            "has_api_key": bool(p.api_key_encrypted),
            "has_oauth_token": bool(p.oauth_token_encrypted),
            "cost_per_unit": p.cost_per_unit,
            "total_calls": p.total_calls,
            "total_cost_usd": p.total_cost_usd,
            "last_health_check": p.last_health_check.isoformat() if p.last_health_check else None,
        }
        for p in providers
    ]


async def get_provider_for_task(
    db: AsyncSession, org_id: uuid.UUID,
    category: str, quality_tier: str = "standard",
) -> Optional[dict]:
    """Get the best available provider for a task category + quality tier.

    Routing logic:
    1. Find providers in this category that are enabled + configured
    2. Filter by quality tier (hero tasks use hero providers, bulk uses bulk)
    3. Sort by priority_order (lower = preferred)
    4. Return the top one
    """
    providers = (await db.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_category == category,
            IntegrationProvider.is_enabled.is_(True),
            IntegrationProvider.health_status.in_(["configured", "healthy"]),
        ).order_by(IntegrationProvider.priority_order)
    )).scalars().all()

    if not providers:
        return None

    # For hero tier: prefer hero providers, fall back to standard
    # For bulk tier: prefer bulk providers, fall back to standard
    # For standard: use standard providers
    tier_match = [p for p in providers if p.quality_tier == quality_tier]
    if tier_match:
        best = tier_match[0]
    elif quality_tier == "hero":
        best = providers[0]  # Best available
    else:
        standard = [p for p in providers if p.quality_tier == "standard"]
        best = standard[0] if standard else providers[0]

    return {
        "provider_key": best.provider_key,
        "provider_name": best.provider_name,
        "api_key": _decrypt(best.api_key_encrypted) if best.api_key_encrypted else None,
        "quality_tier": best.quality_tier,
        "cost_per_unit": best.cost_per_unit,
    }
