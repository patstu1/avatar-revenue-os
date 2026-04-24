"""OAuth connection flow endpoints for YouTube, TikTok, Instagram, and X.

GET  /oauth/connect/{platform}   — Redirect user to platform consent screen
GET  /oauth/callback/{platform}  — Handle callback, exchange code, store tokens
POST /oauth/disconnect/{account_id} — Revoke + clear stored credentials
"""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.audit_service import log_action
from apps.api.services.integration_manager import _encrypt
from packages.clients.oauth_flows import (
    exchange_code,
    get_auth_url,
)
from packages.db.models.accounts import CreatorAccount

logger = structlog.get_logger()

router = APIRouter()

# Supported platforms for OAuth connection
SUPPORTED_PLATFORMS = {"youtube", "tiktok", "instagram", "x"}

# ---------------------------------------------------------------------------
# In-memory state store (swap for Redis in production)
# ---------------------------------------------------------------------------
# Key: state token -> {platform, brand_id, account_id, code_verifier, created_at}
_oauth_state_store: dict[str, dict] = {}


def _get_redirect_uri(platform: str) -> str:
    """Build the callback URI for a platform."""
    base = os.getenv("API_BASE_URL", "http://localhost:8000")
    return f"{base}/api/v1/oauth/callback/{platform}"


def _get_frontend_url() -> str:
    """Return frontend base URL for post-auth redirect."""
    return os.getenv("FRONTEND_URL", "http://localhost:3001")


# ---------------------------------------------------------------------------
# GET /oauth/connect/{platform}
# ---------------------------------------------------------------------------


@router.get("/connect/{platform}")
async def oauth_connect(
    platform: str,
    current_user: OperatorUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(..., description="Brand to connect the account for"),
    account_id: uuid.UUID | None = Query(None, description="Existing account to re-connect"),
):
    """Generate a state token and redirect to the platform's OAuth consent screen."""
    platform = platform.lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform}. Supported: {', '.join(sorted(SUPPORTED_PLATFORMS))}",
        )

    # Verify brand access
    from packages.db.models.core import Brand
    brand = (await db.execute(
        select(Brand).where(Brand.id == brand_id)
    )).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")

    # If reconnecting an existing account, verify it belongs to this brand
    if account_id:
        acct = (await db.execute(
            select(CreatorAccount).where(CreatorAccount.id == account_id)
        )).scalar_one_or_none()
        if not acct or acct.brand_id != brand_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found for this brand")

    # Load platform OAuth app credentials
    client_id = os.getenv(f"{platform.upper()}_OAUTH_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OAuth not configured for {platform}. Set {platform.upper()}_OAUTH_CLIENT_ID env var.",
        )

    redirect_uri = _get_redirect_uri(platform)
    state_token = secrets.token_urlsafe(32)

    auth_result = get_auth_url(
        platform=platform,
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state_token,
    )

    # Persist state for validation on callback
    _oauth_state_store[state_token] = {
        "platform": platform,
        "brand_id": str(brand_id),
        "account_id": str(account_id) if account_id else None,
        "user_id": str(current_user.id),
        "organization_id": str(current_user.organization_id),
        "code_verifier": auth_result.get("code_verifier"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "oauth.connect_initiated",
        platform=platform,
        brand_id=str(brand_id),
        user_id=str(current_user.id),
    )

    return RedirectResponse(url=auth_result["url"], status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# GET /oauth/callback/{platform}
# ---------------------------------------------------------------------------


@router.get("/callback/{platform}")
async def oauth_callback(
    platform: str,
    db: DBSession,
    code: str = Query(..., description="Authorization code from platform"),
    state: str = Query(..., description="State token for CSRF validation"),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    """Handle the OAuth callback: validate state, exchange code, store encrypted tokens."""
    platform = platform.lower()
    frontend_url = _get_frontend_url()

    # Handle explicit errors from the platform
    if error:
        logger.warning("oauth.callback_error", platform=platform, error=error, desc=error_description)
        return RedirectResponse(
            url=f"{frontend_url}/settings/accounts?oauth_error={error}&platform={platform}",
            status_code=status.HTTP_302_FOUND,
        )

    # Validate state token
    state_data = _oauth_state_store.pop(state, None)
    if not state_data:
        logger.warning("oauth.invalid_state", platform=platform)
        return RedirectResponse(
            url=f"{frontend_url}/settings/accounts?oauth_error=invalid_state&platform={platform}",
            status_code=status.HTTP_302_FOUND,
        )

    if state_data["platform"] != platform:
        logger.warning("oauth.platform_mismatch", expected=state_data["platform"], got=platform)
        return RedirectResponse(
            url=f"{frontend_url}/settings/accounts?oauth_error=platform_mismatch&platform={platform}",
            status_code=status.HTTP_302_FOUND,
        )

    # Load OAuth app credentials
    client_id = os.getenv(f"{platform.upper()}_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv(f"{platform.upper()}_OAUTH_CLIENT_SECRET", "")
    redirect_uri = _get_redirect_uri(platform)

    try:
        result = await exchange_code(
            platform=platform,
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=state_data.get("code_verifier"),
        )
    except Exception as exc:
        logger.error("oauth.exchange_failed", platform=platform, error=str(exc))
        return RedirectResponse(
            url=f"{frontend_url}/settings/accounts?oauth_error=exchange_failed&platform={platform}",
            status_code=status.HTTP_302_FOUND,
        )

    user_info = result.get("user_info", {})
    brand_id = uuid.UUID(state_data["brand_id"])
    organization_id = uuid.UUID(state_data["organization_id"])
    user_id = uuid.UUID(state_data["user_id"])

    # ── Create or update CreatorAccount ───────────────────────────────
    account_id = state_data.get("account_id")
    if account_id:
        # Re-connecting an existing account
        acct = (await db.execute(
            select(CreatorAccount).where(CreatorAccount.id == uuid.UUID(account_id))
        )).scalar_one_or_none()
    else:
        acct = None

    if acct:
        # Update existing account with new tokens
        acct.platform_access_token = _encrypt(result["access_token"])
        if result.get("refresh_token"):
            acct.platform_refresh_token = _encrypt(result["refresh_token"])
        acct.platform_token_expires_at = result["expires_at"]
        acct.credential_status = "connected"
        if user_info.get("platform_id"):
            acct.platform_external_id = user_info["platform_id"]
        if user_info.get("username"):
            acct.platform_username = user_info["username"]
    else:
        # Create new account record
        from packages.db.enums import Platform as PlatformEnum

        platform_enum_map = {
            "youtube": PlatformEnum.YOUTUBE,
            "tiktok": PlatformEnum.TIKTOK,
            "instagram": PlatformEnum.INSTAGRAM,
            "x": PlatformEnum.X,
        }
        platform_enum = platform_enum_map.get(platform)
        if not platform_enum:
            platform_enum = PlatformEnum.YOUTUBE  # fallback

        acct = CreatorAccount(
            brand_id=brand_id,
            platform=platform_enum,
            platform_username=user_info.get("username", f"{platform}_user"),
            platform_account_id=user_info.get("platform_id"),
            platform_access_token=_encrypt(result["access_token"]),
            platform_refresh_token=_encrypt(result["refresh_token"]) if result.get("refresh_token") else None,
            platform_token_expires_at=result["expires_at"],
            platform_external_id=user_info.get("platform_id"),
            credential_status="connected",
        )
        db.add(acct)

    await db.flush()
    await db.refresh(acct)

    # Audit trail
    await log_action(
        db,
        "oauth.account_connected",
        organization_id=organization_id,
        brand_id=brand_id,
        user_id=user_id,
        actor_type="human",
        entity_type="creator_account",
        entity_id=acct.id,
        details={
            "platform": platform,
            "platform_username": user_info.get("username"),
            "platform_id": user_info.get("platform_id"),
        },
    )

    logger.info(
        "oauth.account_connected",
        platform=platform,
        account_id=str(acct.id),
        brand_id=str(brand_id),
        username=user_info.get("username"),
    )

    # Redirect to frontend with success
    return RedirectResponse(
        url=f"{frontend_url}/settings/accounts?oauth_success=true&platform={platform}&account_id={acct.id}",
        status_code=status.HTTP_302_FOUND,
    )


# ---------------------------------------------------------------------------
# POST /oauth/disconnect/{account_id}
# ---------------------------------------------------------------------------


@router.post("/disconnect/{account_id}")
async def oauth_disconnect(
    account_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    """Clear stored OAuth credentials for an account."""
    acct = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.id == account_id)
    )).scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Verify brand access
    from packages.db.models.core import Brand
    brand = (await db.execute(
        select(Brand).where(Brand.id == acct.brand_id)
    )).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")

    acct.platform_access_token = None
    acct.platform_refresh_token = None
    acct.platform_token_expires_at = None
    acct.credential_status = "disconnected"
    await db.flush()

    await log_action(
        db,
        "oauth.account_disconnected",
        organization_id=current_user.organization_id,
        brand_id=acct.brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="creator_account",
        entity_id=account_id,
    )

    logger.info("oauth.account_disconnected", account_id=str(account_id))
    return {"account_id": str(account_id), "credential_status": "disconnected"}
