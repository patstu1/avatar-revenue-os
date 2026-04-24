"""Sync credential loader — thin wrapper around integration_manager for Celery workers.

Celery tasks run in sync threads with their own event loops.  This module
provides synchronous helpers that talk directly to the DB via the sync engine,
reusing the same Fernet encryption and .env fallback logic from the async
integration_manager.

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

import os
import uuid
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models.integration_registry import IntegrationProvider

logger = structlog.get_logger()

# Import encryption + env-key mapping from the canonical source
from apps.api.services.integration_manager import (
    _decrypt,
    PROVIDER_ENV_KEYS,
)


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

    # 2. Check provider_secrets (set via dashboard secrets_service — uses different encryption)
    try:
        from sqlalchemy import text
        from apps.api.services.secrets_service import decrypt_value as _decrypt_secrets
        ps_row = session.execute(
            text("SELECT encrypted_value FROM provider_secrets WHERE organization_id = :oid AND provider_name = :pname"),
            {"oid": str(org_id), "pname": provider_key},
        ).fetchone()
        if ps_row and ps_row[0]:
            val = _decrypt_secrets(ps_row[0])
            if val:
                return val
    except Exception:
        pass

    # 3. Fallback: .env transition
    env_var = PROVIDER_ENV_KEYS.get(provider_key)
    if env_var:
        env_value = os.environ.get(env_var, "")
        if env_value:
            logger.warning(
                "credential_env_fallback_DEPRECATED",
                provider=provider_key,
                env_var=env_var,
                hint="Migrate to DB credentials via Settings > Integrations",
            )
            return env_value
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
        env_var = PROVIDER_ENV_KEYS.get(best.provider_key)
        if env_var:
            env_value = os.environ.get(env_var, "")
            if env_value:
                logger.warning(
                    "credential_env_fallback_DEPRECATED",
                    provider=best.provider_key,
                    env_var=env_var,
                )
                api_key = env_value

    return {
        "provider_key": best.provider_key,
        "provider_name": best.provider_name,
        "api_key": api_key,
        "quality_tier": best.quality_tier,
        "cost_per_unit": best.cost_per_unit,
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
        env_var = PROVIDER_ENV_KEYS.get(provider_key)
        if env_var:
            env_value = os.environ.get(env_var, "")
            if env_value:
                logger.warning(
                    "credential_env_fallback_DEPRECATED",
                    provider=provider_key,
                    env_var=env_var,
                )
                result["api_key"] = env_value

    return result
