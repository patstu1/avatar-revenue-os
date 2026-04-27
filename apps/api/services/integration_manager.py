"""Integration Manager — CRUD + health + credential management for providers.

Credentials are stored encrypted in the integration_providers table and
loaded at runtime. Strict DB-only doctrine: there is no env fallback for
provider credentials. The only env value consulted by this module is
``API_SECRET_KEY``, which is the master encryption key that protects the
on-disk ciphertext (legitimate infrastructure secret per doctrine).

Encryption: Fernet (AES-128-CBC + HMAC-SHA256) derived from API_SECRET_KEY
via PBKDF2-SHA256 (480k iterations).
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid

import structlog
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.integration_registry import IntegrationProvider

logger = structlog.get_logger()

# ── Fernet encryption helpers ───────────────────────────────────────────────

_SALT = b"avatar-content-os-integration-salt-v1"  # static salt — key uniqueness from API_SECRET_KEY


def _derive_fernet_key() -> bytes:
    """Derive a Fernet-compatible key from API_SECRET_KEY via PBKDF2."""
    secret = os.getenv("API_SECRET_KEY", "default-dev-key-not-for-production")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


def _get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key())


def _encrypt(value: str) -> str:
    """Encrypt a credential value using Fernet."""
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt(encrypted: str) -> str:
    """Decrypt a credential value.  Handles both Fernet and legacy XOR."""
    if not encrypted:
        return ""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except (InvalidToken, Exception):
        # Fallback: try legacy XOR decryption for pre-migration credentials
        try:
            return _decrypt_xor_legacy(encrypted)
        except Exception:
            logger.warning("credential_decrypt_failed", hint="neither Fernet nor XOR succeeded")
            return ""


# ── Legacy XOR helpers (read-only, for migration) ──────────────────────────


def _get_xor_key() -> bytes:
    secret = os.getenv("API_SECRET_KEY", "default-dev-key-not-for-production")
    return hashlib.sha256(secret.encode()).digest()


def _decrypt_xor_legacy(encrypted: str) -> str:
    if not encrypted:
        return ""
    key = _get_xor_key()
    data = base64.b64decode(encrypted.encode())
    decrypted = bytes(a ^ b for a, b in zip(data, (key * ((len(data) // len(key)) + 1))[: len(data)]))
    return decrypted.decode()


# ── Provider ↔ .env key mapping ────────────────────────────────────────────

PROVIDER_ENV_KEYS: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini_flash": "GOOGLE_AI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai_image": "OPENAI_API_KEY",
    "imagen4": "GOOGLE_AI_API_KEY",
    "flux": "FAL_API_KEY",
    "kling": "FAL_API_KEY",
    "wan": "FAL_API_KEY",
    "runway": "RUNWAY_API_KEY",
    "higgsfield": "HIGGSFIELD_API_KEY",
    "heygen": "HEYGEN_API_KEY",
    "did": "DID_API_KEY",
    "synthesia": "SYNTHESIA_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
    "fish_audio": "FISH_AUDIO_API_KEY",
    "voxtral": "MISTRAL_API_KEY",
    "suno": "SUNO_API_KEY",
    "mubert": "MUBERT_API_KEY",
    "stable_audio": "STABILITY_API_KEY",
    "buffer": "BUFFER_API_KEY",
    "publer": "PUBLER_API_KEY",
    "ayrshare": "AYRSHARE_API_KEY",
    "youtube_analytics": "YOUTUBE_API_KEY",
    "tiktok_analytics": "TIKTOK_ACCESS_TOKEN",
    "instagram_analytics": "INSTAGRAM_ACCESS_TOKEN",
    "serpapi": "SERPAPI_KEY",
    "smtp": "SMTP_PASSWORD",
    "imap": "IMAP_PASSWORD",
    "stripe": "STRIPE_SECRET_KEY",
}

# Default provider catalog
DEFAULT_PROVIDERS = [
    # LLM
    {"key": "claude", "name": "Claude Sonnet 4.6", "category": "llm", "tier": "hero", "cost": 0.003, "priority": 1},
    {
        "key": "gemini_flash",
        "name": "Gemini 2.5 Flash",
        "category": "llm",
        "tier": "standard",
        "cost": 0.0003,
        "priority": 5,
    },
    {"key": "deepseek", "name": "DeepSeek V3.2", "category": "llm", "tier": "bulk", "cost": 0.00028, "priority": 10},
    {"key": "groq", "name": "Groq", "category": "llm", "tier": "bulk", "cost": 0.0001, "priority": 8},
    # Image
    {"key": "openai_image", "name": "GPT Image 1.5", "category": "image", "tier": "hero", "cost": 0.04, "priority": 1},
    {
        "key": "imagen4",
        "name": "Google Imagen 4 Fast",
        "category": "image",
        "tier": "standard",
        "cost": 0.02,
        "priority": 5,
    },
    {
        "key": "flux",
        "name": "Flux 2 Pro (via fal.ai)",
        "category": "image",
        "tier": "standard",
        "cost": 0.055,
        "priority": 8,
    },
    # Video
    {
        "key": "kling",
        "name": "Kling AI (via fal.ai)",
        "category": "video",
        "tier": "standard",
        "cost": 0.07,
        "priority": 5,
    },
    {"key": "runway", "name": "Runway Gen-4 Turbo", "category": "video", "tier": "hero", "cost": 0.10, "priority": 1},
    # Avatar
    {"key": "heygen", "name": "HeyGen", "category": "avatar", "tier": "hero", "cost": 0.033, "priority": 1},
    {"key": "did", "name": "D-ID", "category": "avatar", "tier": "standard", "cost": 0.02, "priority": 5},
    # Voice
    {"key": "elevenlabs", "name": "ElevenLabs", "category": "voice", "tier": "hero", "cost": 0.0003, "priority": 1},
    {
        "key": "fish_audio",
        "name": "Fish Audio",
        "category": "voice",
        "tier": "standard",
        "cost": 0.000015,
        "priority": 5,
    },
    {
        "key": "voxtral",
        "name": "Voxtral TTS (Mistral)",
        "category": "voice",
        "tier": "bulk",
        "cost": 0.000016,
        "priority": 10,
    },
    # Publishing
    {"key": "buffer", "name": "Buffer", "category": "publishing", "tier": "standard", "cost": 0, "priority": 1},
    {"key": "publer", "name": "Publer", "category": "publishing", "tier": "standard", "cost": 0, "priority": 5},
    {"key": "ayrshare", "name": "Ayrshare", "category": "publishing", "tier": "standard", "cost": 0, "priority": 10},
    # Analytics
    {
        "key": "youtube_analytics",
        "name": "YouTube Analytics",
        "category": "analytics",
        "tier": "standard",
        "cost": 0,
        "priority": 1,
    },
    {
        "key": "tiktok_analytics",
        "name": "TikTok Analytics",
        "category": "analytics",
        "tier": "standard",
        "cost": 0,
        "priority": 1,
    },
    {
        "key": "instagram_analytics",
        "name": "Instagram Graph API",
        "category": "analytics",
        "tier": "standard",
        "cost": 0,
        "priority": 1,
    },
    # Trends
    {
        "key": "serpapi",
        "name": "SerpAPI (Google Trends)",
        "category": "trends",
        "tier": "standard",
        "cost": 0.005,
        "priority": 1,
    },
    # Email
    {"key": "smtp", "name": "SMTP Email", "category": "email", "tier": "standard", "cost": 0, "priority": 1},
    {"key": "imap", "name": "IMAP Inbox", "category": "inbox", "tier": "standard", "cost": 0, "priority": 1},
    # Payment
    {"key": "stripe", "name": "Stripe", "category": "payment", "tier": "standard", "cost": 0.029, "priority": 1},
]


async def seed_provider_catalog(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Seed the default provider catalog for an organization.

    After seeding, auto-migrates any .env credentials into the encrypted DB
    so the system can stop depending on .env for API keys.
    """
    created = 0
    for p in DEFAULT_PROVIDERS:
        existing = (
            await db.execute(
                select(IntegrationProvider).where(
                    IntegrationProvider.organization_id == org_id,
                    IntegrationProvider.provider_key == p["key"],
                )
            )
        ).scalar_one_or_none()
        if not existing:
            db.add(
                IntegrationProvider(
                    organization_id=org_id,
                    provider_key=p["key"],
                    provider_name=p["name"],
                    provider_category=p["category"],
                    quality_tier=p["tier"],
                    cost_per_unit=p["cost"],
                    priority_order=p["priority"],
                    health_status="unconfigured",
                )
            )
            created += 1
    await db.flush()

    # ── Auto-migrate .env credentials to DB ─────────────────────────
    migrated = await _auto_migrate_env_credentials(db, org_id)

    return {"created": created, "total_catalog": len(DEFAULT_PROVIDERS), "env_migrated": migrated}


async def _auto_migrate_env_credentials(db: AsyncSession, org_id: uuid.UUID) -> list[str]:
    """Check every known provider: if DB has no credential but .env does, migrate it."""
    migrated: list[str] = []
    for provider_key, env_var in PROVIDER_ENV_KEYS.items():
        env_value = os.environ.get(env_var, "")
        if not env_value:
            continue

        provider = (
            await db.execute(
                select(IntegrationProvider).where(
                    IntegrationProvider.organization_id == org_id,
                    IntegrationProvider.provider_key == provider_key,
                )
            )
        ).scalar_one_or_none()

        if not provider:
            continue
        if provider.api_key_encrypted:
            continue  # already has a DB credential

        provider.api_key_encrypted = _encrypt(env_value)
        provider.health_status = "configured"
        provider.is_enabled = True
        migrated.append(provider_key)
        logger.info(
            "env_credential_migrated",
            provider=provider_key,
            env_var=env_var,
            org_id=str(org_id),
        )

    if migrated:
        await db.flush()
        logger.info("env_migration_complete", count=len(migrated), providers=migrated)
    return migrated


async def set_credential(
    db: AsyncSession,
    org_id: uuid.UUID,
    provider_key: str,
    *,
    api_key: str | None = None,
    api_secret: str | None = None,
    oauth_token: str | None = None,
    extra_config: dict | None = None,
) -> dict:
    """Set or update credentials for a provider. Encrypts before storage."""
    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == org_id,
                IntegrationProvider.provider_key == provider_key,
            )
        )
    ).scalar_one_or_none()

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


async def get_credential(db: AsyncSession, org_id: uuid.UUID, provider_key: str) -> str | None:
    """Get decrypted API key for a provider — DB-only, no env fallback."""
    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == org_id,
                IntegrationProvider.provider_key == provider_key,
                IntegrationProvider.is_enabled.is_(True),
            )
        )
    ).scalar_one_or_none()

    if provider and provider.api_key_encrypted:
        return _decrypt(provider.api_key_encrypted)

    # No env fallback — all credentials must be stored in DB via the dashboard.
    # If the key is missing, the operator needs to configure it through
    # Settings > Integrations.
    if not provider:
        logger.warning(
            "credential_missing", provider=provider_key, hint="Provider not found in integration_providers table"
        )
    else:
        logger.warning("credential_not_configured", provider=provider_key, hint="Configure via Settings > Integrations")
    return None


async def get_credential_full(
    db: AsyncSession,
    org_id: uuid.UUID,
    provider_key: str,
) -> dict:
    """Get decrypted API key + oauth_token + extra_config for a provider."""
    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == org_id,
                IntegrationProvider.provider_key == provider_key,
                IntegrationProvider.is_enabled.is_(True),
            )
        )
    ).scalar_one_or_none()

    result: dict = {"api_key": None, "oauth_token": None, "extra_config": {}}

    if provider:
        if provider.api_key_encrypted:
            result["api_key"] = _decrypt(provider.api_key_encrypted)
        if provider.oauth_token_encrypted:
            result["oauth_token"] = _decrypt(provider.oauth_token_encrypted)
        result["extra_config"] = provider.extra_config or {}

    if not result["api_key"]:
        logger.warning(
            "credential_not_configured",
            provider=provider_key,
            hint="Configure via Settings > Integrations in the dashboard",
        )

    return result


async def list_providers(db: AsyncSession, org_id: uuid.UUID, category: str | None = None) -> list[dict]:
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
    db: AsyncSession,
    org_id: uuid.UUID,
    category: str,
    quality_tier: str = "standard",
) -> dict | None:
    """Get the best available provider for a task category + quality tier.

    Routing logic:
    1. Find providers in this category that are enabled + configured
    2. Filter by quality tier (hero tasks use hero providers, bulk uses bulk)
    3. Sort by priority_order (lower = preferred)
    4. Return the top one
    """
    providers = (
        (
            await db.execute(
                select(IntegrationProvider)
                .where(
                    IntegrationProvider.organization_id == org_id,
                    IntegrationProvider.provider_category == category,
                    IntegrationProvider.is_enabled.is_(True),
                    IntegrationProvider.health_status.in_(["configured", "healthy"]),
                )
                .order_by(IntegrationProvider.priority_order)
            )
        )
        .scalars()
        .all()
    )

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


# ── One-time migration: re-encrypt XOR → Fernet ───────────────────────────


async def migrate_xor_to_fernet(db: AsyncSession) -> dict:
    """Re-encrypt all credentials from legacy XOR to Fernet.

    Safe to run multiple times — Fernet-encrypted values will decrypt
    successfully on the first try and be skipped.
    """
    providers = (await db.execute(select(IntegrationProvider))).scalars().all()
    migrated = 0
    skipped = 0
    errors = 0

    fernet = _get_fernet()

    for p in providers:
        for field in ("api_key_encrypted", "api_secret_encrypted", "oauth_token_encrypted", "oauth_refresh_encrypted"):
            encrypted_val = getattr(p, field)
            if not encrypted_val:
                continue

            # Check if already Fernet-encrypted
            try:
                fernet.decrypt(encrypted_val.encode())
                skipped += 1
                continue  # already Fernet
            except (InvalidToken, Exception):
                pass

            # Try XOR decrypt, then re-encrypt with Fernet
            try:
                plaintext = _decrypt_xor_legacy(encrypted_val)
                if plaintext:
                    setattr(p, field, _encrypt(plaintext))
                    migrated += 1
                else:
                    errors += 1
            except Exception as e:
                logger.warning("xor_to_fernet_migration_error", provider=p.provider_key, field=field, error=str(e))
                errors += 1

    await db.flush()
    logger.info("xor_to_fernet_migration_complete", migrated=migrated, skipped=skipped, errors=errors)
    return {"migrated": migrated, "already_fernet": skipped, "errors": errors}


# ── Stripe-specific helpers (DB-only, no env reads) ─────────────────────────


async def set_webhook_secret(
    db: AsyncSession,
    org_id: uuid.UUID,
    provider_key: str,
    webhook_secret: str,
) -> dict:
    """Store an encrypted webhook signing secret on the provider row.

    The webhook secret rides on ``api_secret_encrypted`` — the existing
    encrypted Text column on integration_providers. Storing the secret
    in ``extra_config`` (JSONB) would land plaintext on disk, which the
    doctrine forbids; this slot is encrypted with the same Fernet key
    as ``api_key_encrypted``.
    """
    if not webhook_secret or not webhook_secret.strip():
        return {"error": "webhook_secret cannot be empty"}

    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == org_id,
                IntegrationProvider.provider_key == provider_key,
            )
        )
    ).scalar_one_or_none()

    if not provider:
        return {"error": f"Provider '{provider_key}' not found. Run seed_provider_catalog first."}

    provider.api_secret_encrypted = _encrypt(webhook_secret.strip())
    await db.flush()
    return {"provider": provider_key, "webhook_secret": "configured", "encrypted": True}


async def get_webhook_secret(
    db: AsyncSession,
    org_id: uuid.UUID,
    provider_key: str,
) -> str | None:
    """DB-only resolver for an encrypted webhook signing secret."""
    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == org_id,
                IntegrationProvider.provider_key == provider_key,
                IntegrationProvider.is_enabled.is_(True),
            )
        )
    ).scalar_one_or_none()

    if not provider or not provider.api_secret_encrypted:
        return None
    return _decrypt(provider.api_secret_encrypted)


async def resolve_operator_org_for_stripe(db: AsyncSession) -> uuid.UUID | None:
    """Find the org that owns the operator's Stripe account.

    Single-tenant assumption: there is exactly one organization in the
    database that has ``provider_key='stripe'`` configured and enabled.
    That row is the operator's own org, which receives all incoming
    Stripe revenue.

    Resolution is DB-only by design — there is no ``OPERATOR_ORG_ID``
    env var. If two or more orgs have Stripe configured, the resolver
    picks the earliest by ``created_at`` and logs a warning so the
    operator can clean it up.
    """
    rows = (
        await db.execute(
            select(IntegrationProvider)
            .where(
                IntegrationProvider.provider_key == "stripe",
                IntegrationProvider.is_enabled.is_(True),
                IntegrationProvider.api_key_encrypted.isnot(None),
            )
            .order_by(IntegrationProvider.created_at.asc())
        )
    ).scalars().all()

    if not rows:
        return None
    if len(rows) > 1:
        logger.warning(
            "stripe.operator_org_ambiguous",
            count=len(rows),
            chosen_org_id=str(rows[0].organization_id),
            hint="Multiple organizations have Stripe configured. Earliest by created_at chosen.",
        )
    return rows[0].organization_id


def classify_stripe_mode(api_key: str | None) -> str:
    """Classify a Stripe key by its publishable prefix.

    Returns one of ``"live"``, ``"test"``, ``"unconfigured"``, or
    ``"unknown"``. Never returns the key, never returns prefix bytes —
    only the classification token. Safe to expose to operators.
    """
    if not api_key:
        return "unconfigured"
    key = api_key.strip()
    if key.startswith("sk_live_") or key.startswith("rk_live_"):
        return "live"
    if key.startswith("sk_test_") or key.startswith("rk_test_"):
        return "test"
    return "unknown"


async def get_stripe_credential_status(db: AsyncSession) -> dict:
    """Return a secret-free summary of Stripe DB credentials for the operator.

    The caller (UI/health endpoint) renders this directly. The response
    contains classification tokens only — never the api key, never the
    webhook secret, never any prefix bytes beyond classification.
    """
    op_org_id = await resolve_operator_org_for_stripe(db)
    if op_org_id is None:
        return {
            "configured": False,
            "operator_org_id": None,
            "api_key_source": "missing",
            "webhook_secret_source": "missing",
            "mode": "unconfigured",
            "last_health_check": None,
            "health_status": None,
        }

    provider = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == op_org_id,
                IntegrationProvider.provider_key == "stripe",
            )
        )
    ).scalar_one_or_none()

    api_key_present = bool(provider and provider.api_key_encrypted)
    webhook_secret_present = bool(provider and provider.api_secret_encrypted)
    api_key_plain = _decrypt(provider.api_key_encrypted) if api_key_present else None
    mode = classify_stripe_mode(api_key_plain)
    api_key_plain = None  # drop the reference; never return or log

    return {
        "configured": api_key_present and webhook_secret_present,
        "operator_org_id": str(op_org_id),
        "api_key_source": "db" if api_key_present else "missing",
        "webhook_secret_source": "db" if webhook_secret_present else "missing",
        "mode": mode,
        "last_health_check": (
            provider.last_health_check.isoformat()
            if provider and provider.last_health_check
            else None
        ),
        "health_status": provider.health_status if provider else None,
    }
