"""Sync credential loader — thin wrapper around integration_manager for Celery workers.

Celery tasks run in sync threads with their own event loops. This module
provides synchronous helpers that talk directly to the DB via the sync engine,
reusing the same Fernet encryption as the async integration_manager.

STRICT DB-ONLY POLICY: There is no env fallback for provider credentials.
All provider API keys must be stored in integration_providers (or written by
the settings router into both integration_providers and provider_secrets).
If a credential is not in the DB, the loader returns None and the caller
is expected to skip the task with a clear 'not_configured' log line.

Usage in a worker task::

    from packages.clients.credential_loader import load_credential, load_credential_for_task

    # Direct lookup by provider key
    api_key = load_credential(session, org_id, "claude")

    # Routing lookup: best provider for category + tier
    result = load_credential_for_task(session, org_id, "llm", "hero")
    api_key = result["api_key"]
    provider_key = result["provider_key"]
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models.integration_registry import IntegrationProvider

logger = structlog.get_logger()

# Import encryption from the canonical source
from apps.api.services.integration_manager import _decrypt


def load_credential(session: Session, org_id: uuid.UUID, provider_key: str) -> Optional[str]:
    """Synchronous: get decrypted API key for a provider.

    Lookup order:
    1. integration_providers (primary credential store)
    2. provider_secrets (dashboard-set credentials via secrets_service)
    3. .env variable (legacy fallback)
    """
    # 1. Check integration_providers
    provider = session.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_key == provider_key,
            IntegrationProvider.is_enabled.is_(True),
        )
    ).scalar_one_or_none()

    if provider and provider.api_key_encrypted:
        return _decrypt(provider.api_key_encrypted)

    # No env fallback — all credentials must be in the DB (integration_providers).
    # Configure via Settings > Integrations in the dashboard.
    if not provider:
        logger.warning("credential_missing", provider=provider_key, hint="Not found in integration_providers")
    else:
        logger.warning("credential_not_configured", provider=provider_key, hint="Configure via Settings > Integrations")
    return None


def load_credential_for_task(
    session: Session,
    org_id: uuid.UUID,
    category: str,
    quality_tier: str = "standard",
) -> Optional[dict]:
    """Synchronous: route to best provider for category + tier, return key + metadata.

    Returns dict with: provider_key, provider_name, api_key, quality_tier, cost_per_unit
    or None if nothing is available.
    """
    providers = session.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_category == category,
            IntegrationProvider.is_enabled.is_(True),
            IntegrationProvider.health_status.in_(["configured", "healthy"]),
        ).order_by(IntegrationProvider.priority_order)
    ).scalars().all()

    if not providers:
        return None

    tier_match = [p for p in providers if p.quality_tier == quality_tier]
    if tier_match:
        best = tier_match[0]
    elif quality_tier == "hero":
        best = providers[0]
    else:
        standard = [p for p in providers if p.quality_tier == "standard"]
        best = standard[0] if standard else providers[0]

    api_key = _decrypt(best.api_key_encrypted) if best.api_key_encrypted else None

    if not api_key:
        logger.warning(
            "credential_not_configured",
            provider=best.provider_key,
            hint="Configure via Settings > Integrations in the dashboard",
        )

    return {
        "provider_key": best.provider_key,
        "provider_name": best.provider_name,
        "api_key": api_key,
        "quality_tier": best.quality_tier,
        "cost_per_unit": best.cost_per_unit,
    }


def load_smtp_config(session: Session, org_id: uuid.UUID) -> Optional[dict]:
    """Resolve SMTP config for an org from integration_providers (sync).

    System-managed-first: the dashboard writes an integration_providers row with
    provider_key='smtp', api_key_encrypted holding the SMTP password, and
    extra_config holding host/port/username/from_email/use_tls. Returns that
    dict. Env is never consulted here; callers decide if an env-legacy
    fallback is acceptable (see SmtpEmailClient.from_env_legacy).

    Returns None if no DB-managed SMTP config is present.
    """
    provider = session.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_key == "smtp",
            IntegrationProvider.is_enabled.is_(True),
        )
    ).scalar_one_or_none()

    if not provider:
        return None

    extra = provider.extra_config or {}
    host = extra.get("host") or extra.get("smtp_host")
    from_email = extra.get("from_email") or extra.get("smtp_from_email")

    if not host or not from_email:
        logger.warning(
            "smtp.db_config_incomplete",
            org_id=str(org_id),
            hint="integration_providers.extra_config must include host and from_email",
        )
        return None

    password = _decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else ""
    use_tls_raw = extra.get("use_tls", True)
    if isinstance(use_tls_raw, str):
        use_tls = use_tls_raw.lower() not in ("false", "0", "no", "off")
    else:
        use_tls = bool(use_tls_raw)

    return {
        "host": host,
        "port": int(extra.get("port") or extra.get("smtp_port") or 587),
        "username": extra.get("username") or extra.get("smtp_username") or "",
        "password": password,
        "from_email": from_email,
        "use_tls": use_tls,
        "source": "db",
    }


async def load_smtp_config_async(session, org_id: uuid.UUID) -> Optional[dict]:
    """Async variant of load_smtp_config for FastAPI request-path callers."""
    from apps.api.services.integration_manager import get_credential_full

    full = await get_credential_full(session, org_id, "smtp")
    extra = full.get("extra_config") or {}
    host = extra.get("host") or extra.get("smtp_host")
    from_email = extra.get("from_email") or extra.get("smtp_from_email")
    if not host or not from_email:
        return None

    use_tls_raw = extra.get("use_tls", True)
    if isinstance(use_tls_raw, str):
        use_tls = use_tls_raw.lower() not in ("false", "0", "no", "off")
    else:
        use_tls = bool(use_tls_raw)

    return {
        "host": host,
        "port": int(extra.get("port") or extra.get("smtp_port") or 587),
        "username": extra.get("username") or extra.get("smtp_username") or "",
        "password": full.get("api_key") or "",
        "from_email": from_email,
        "use_tls": use_tls,
        "source": "db",
    }


def load_credential_full(session: Session, org_id: uuid.UUID, provider_key: str) -> dict:
    """Synchronous: get api_key + oauth_token + extra_config for a provider."""
    provider = session.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_key == provider_key,
            IntegrationProvider.is_enabled.is_(True),
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
