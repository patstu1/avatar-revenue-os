"""Platform-specific OAuth 2.0 helpers for YouTube, TikTok, Instagram, and X.

Each platform has its own authorization URL format, token exchange endpoint,
scope set, and refresh mechanism. This module normalizes them behind three
functions: get_auth_url, exchange_code, refresh_access_token.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Platform configuration
# ---------------------------------------------------------------------------

PLATFORM_CONFIG = {
    "youtube": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ],
        "user_info_url": "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        "uses_pkce": False,
    },
    "tiktok": {
        "authorize_url": "https://www.tiktok.com/v2/auth/authorize/",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "scopes": [
            "user.info.basic",
            "video.upload",
            "video.list",
        ],
        "user_info_url": "https://open.tiktokapis.com/v2/user/info/?fields=open_id,union_id,avatar_url,display_name",
        "uses_pkce": True,
    },
    "instagram": {
        "authorize_url": "https://www.facebook.com/v21.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v21.0/oauth/access_token",
        "scopes": [
            "instagram_basic",
            "instagram_content_publish",
            "pages_show_list",
            "pages_read_engagement",
        ],
        "user_info_url": "https://graph.facebook.com/v21.0/me?fields=id,name",
        "uses_pkce": False,
    },
    "x": {
        "authorize_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.x.com/2/oauth2/token",
        "scopes": [
            "tweet.read",
            "tweet.write",
            "users.read",
            "offline.access",
        ],
        "user_info_url": "https://api.x.com/2/users/me",
        "uses_pkce": True,
    },
}

# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


# ---------------------------------------------------------------------------
# get_auth_url
# ---------------------------------------------------------------------------


def get_auth_url(
    platform: str,
    client_id: str,
    redirect_uri: str,
    state: str | None = None,
    code_verifier: str | None = None,
) -> dict:
    """Build the authorization URL the user should be redirected to.

    Returns:
        {
            "url": "https://...",
            "state": "<state token>",
            "code_verifier": "<if PKCE platform, else None>",
        }
    """
    platform = platform.lower()
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise ValueError(f"Unsupported OAuth platform: {platform}")

    if state is None:
        state = secrets.token_urlsafe(32)

    params: dict[str, str] = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }

    verifier_out: str | None = None

    if platform == "youtube":
        params["client_id"] = client_id
        params["scope"] = " ".join(cfg["scopes"])
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    elif platform == "tiktok":
        params["client_key"] = client_id
        params["scope"] = ",".join(cfg["scopes"])
        verifier_out, challenge = (code_verifier, None) if code_verifier else (None, None)
        if not verifier_out:
            verifier_out, challenge = generate_pkce_pair()
        else:
            digest = hashlib.sha256(verifier_out.encode("ascii")).digest()
            challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"

    elif platform == "instagram":
        params["client_id"] = client_id
        params["scope"] = ",".join(cfg["scopes"])

    elif platform == "x":
        params["client_id"] = client_id
        params["scope"] = " ".join(cfg["scopes"])
        verifier_out, challenge = (code_verifier, None) if code_verifier else (None, None)
        if not verifier_out:
            verifier_out, challenge = generate_pkce_pair()
        else:
            digest = hashlib.sha256(verifier_out.encode("ascii")).digest()
            challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"

    url = f"{cfg['authorize_url']}?{urlencode(params)}"
    return {"url": url, "state": state, "code_verifier": verifier_out}


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


async def exchange_code(
    platform: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str | None = None,
) -> dict:
    """Exchange authorization code for tokens + basic user info.

    Returns:
        {
            "access_token": "...",
            "refresh_token": "..." or None,
            "expires_at": datetime (UTC),
            "user_info": { platform-specific profile data },
        }
    """
    platform = platform.lower()
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise ValueError(f"Unsupported OAuth platform: {platform}")

    token_data: dict = {}

    async with httpx.AsyncClient(timeout=30) as client:
        # ── Token exchange ────────────────────────────────────────────
        if platform == "youtube":
            resp = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

        elif platform == "tiktok":
            resp = await client.post(
                cfg["token_url"],
                json={
                    "client_key": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier or "",
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

        elif platform == "instagram":
            resp = await client.get(
                cfg["token_url"],
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

        elif platform == "x":
            resp = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier or "",
                },
                auth=(client_id, client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            token_data = resp.json()

        # ── Normalize token response ──────────────────────────────────
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        # TikTok nests tokens under "data"
        if platform == "tiktok" and "data" in token_data:
            nested = token_data["data"]
            access_token = nested.get("access_token", access_token)
            refresh_token = nested.get("refresh_token", refresh_token)
            expires_in = nested.get("expires_in", expires_in)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

        # ── Fetch user info ───────────────────────────────────────────
        user_info = await _fetch_user_info(client, platform, cfg, access_token)

    logger.info("oauth_code_exchanged", platform=platform, has_refresh=bool(refresh_token))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "user_info": user_info,
    }


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------


async def refresh_access_token(
    platform: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    """Refresh an expired access token.

    Returns:
        {
            "access_token": "...",
            "refresh_token": "..." (may be rotated),
            "expires_at": datetime (UTC),
        }
    """
    platform = platform.lower()
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise ValueError(f"Unsupported OAuth platform: {platform}")

    async with httpx.AsyncClient(timeout=30) as client:
        if platform == "youtube":
            resp = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        elif platform == "tiktok":
            resp = await client.post(
                cfg["token_url"],
                json={
                    "client_key": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        elif platform == "instagram":
            # Facebook long-lived token refresh
            resp = await client.get(
                "https://graph.facebook.com/v21.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "fb_exchange_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        elif platform == "x":
            resp = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                },
                auth=(client_id, client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

        else:
            raise ValueError(f"Unsupported platform for refresh: {platform}")

    # Normalize
    new_access = data.get("access_token", "")
    new_refresh = data.get("refresh_token", refresh_token)  # keep old if not rotated
    expires_in = data.get("expires_in", 3600)

    if platform == "tiktok" and "data" in data:
        nested = data["data"]
        new_access = nested.get("access_token", new_access)
        new_refresh = nested.get("refresh_token", new_refresh)
        expires_in = nested.get("expires_in", expires_in)

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    logger.info("oauth_token_refreshed", platform=platform)
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "expires_at": expires_at,
    }


# ---------------------------------------------------------------------------
# ensure_valid_token
# ---------------------------------------------------------------------------


async def ensure_valid_token(db, account) -> str | None:
    """Check if a CreatorAccount's access token is still valid; auto-refresh if expired.

    Args:
        db: AsyncSession
        account: CreatorAccount ORM object (must have platform_access_token,
                 platform_refresh_token, platform_token_expires_at fields)

    Returns:
        A valid access_token string, or None if refresh failed / no credentials.
    """
    from apps.api.services.integration_manager import _encrypt

    if not account.platform_access_token:
        logger.warning("ensure_valid_token.no_token", account_id=str(account.id))
        return None

    # If no expiry recorded, assume it is valid (caller will find out on 401)
    if account.platform_token_expires_at is None:
        return account.platform_access_token

    now = datetime.now(timezone.utc)
    # Refresh 5 minutes early to avoid edge-case expiry during request
    buffer = timedelta(minutes=5)

    if account.platform_token_expires_at > now + buffer:
        # Token still valid
        return account.platform_access_token

    # ── Token expired — attempt refresh ───────────────────────────────
    if not account.platform_refresh_token:
        logger.warning("ensure_valid_token.no_refresh_token", account_id=str(account.id))
        account.credential_status = "expired"
        await db.flush()
        return None

    platform_val = account.platform.value if hasattr(account.platform, "value") else str(account.platform)

    # Resolve platform OAuth client credentials from env
    # These should be app-level credentials (not per-user)
    client_id, client_secret = _get_platform_oauth_creds(platform_val)
    if not client_id or not client_secret:
        logger.error(
            "ensure_valid_token.missing_platform_creds",
            platform=platform_val,
            account_id=str(account.id),
        )
        account.credential_status = "error"
        await db.flush()
        return None

    try:
        result = await refresh_access_token(
            platform=platform_val,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=account.platform_refresh_token,
        )

        # Store refreshed tokens (encrypted)
        account.platform_access_token = _encrypt(result["access_token"])
        if result.get("refresh_token"):
            account.platform_refresh_token = _encrypt(result["refresh_token"])
        account.platform_token_expires_at = result["expires_at"]
        account.credential_status = "connected"
        await db.flush()

        logger.info(
            "ensure_valid_token.refreshed",
            platform=platform_val,
            account_id=str(account.id),
            new_expiry=result["expires_at"].isoformat(),
        )
        return result["access_token"]

    except Exception as exc:
        logger.error(
            "ensure_valid_token.refresh_failed",
            platform=platform_val,
            account_id=str(account.id),
            error=str(exc),
        )
        account.credential_status = "expired"
        await db.flush()

        # Emit alert event for monitoring
        try:
            from apps.api.services.audit_service import log_action

            await log_action(
                db,
                "oauth.token_refresh_failed",
                organization_id=account.brand_id,  # best-effort org reference
                entity_type="creator_account",
                entity_id=account.id,
                actor_type="system",
                details={"platform": platform_val, "error": str(exc)},
            )
        except Exception:
            pass  # audit failure should not break caller

        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_platform_oauth_creds(platform: str) -> tuple[str, str]:
    """Load app-level OAuth client_id / client_secret from environment."""
    import os

    prefix = platform.upper()
    client_id = os.getenv(f"{prefix}_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv(f"{prefix}_OAUTH_CLIENT_SECRET", "")
    return client_id, client_secret


async def _fetch_user_info(
    client: httpx.AsyncClient,
    platform: str,
    cfg: dict,
    access_token: str,
) -> dict:
    """Fetch basic user profile after token exchange."""
    try:
        if platform == "youtube":
            resp = await client.get(
                cfg["user_info_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if items:
                snippet = items[0].get("snippet", {})
                return {
                    "platform_id": items[0].get("id", ""),
                    "username": snippet.get("title", ""),
                    "display_name": snippet.get("title", ""),
                    "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                }

        elif platform == "tiktok":
            resp = await client.get(
                cfg["user_info_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {}).get("user", {})
            return {
                "platform_id": data.get("open_id", ""),
                "username": data.get("display_name", ""),
                "display_name": data.get("display_name", ""),
                "avatar_url": data.get("avatar_url", ""),
            }

        elif platform == "instagram":
            resp = await client.get(
                cfg["user_info_url"],
                params={"access_token": access_token},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "platform_id": data.get("id", ""),
                "username": data.get("name", ""),
                "display_name": data.get("name", ""),
            }

        elif platform == "x":
            resp = await client.get(
                cfg["user_info_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "platform_id": data.get("id", ""),
                "username": data.get("username", ""),
                "display_name": data.get("name", ""),
            }

    except Exception as exc:
        logger.warning("oauth_user_info_fetch_failed", platform=platform, error=str(exc))

    return {}
