"""Microsoft 365 OAuth 2.0 flow for mailbox IMAP/SMTP access.

Separate from packages/clients/oauth_flows.py (which targets social platforms
keyed to CreatorAccount). This module targets mailbox access keyed to
InboxConnection, with credentials loaded from integration_providers.

Flow:
    1. build_auth_url(org_id, email_hint) → URL to redirect user to
    2. User consents → Microsoft redirects to /oauth/callback/microsoft?code=...
    3. exchange_code(org_id, code) → access_token + refresh_token
    4. Tokens stored on InboxConnection (encrypted)
    5. Periodically: refresh_access_token(org_id, refresh_token) → new access_token

Scopes requested:
    - https://outlook.office.com/IMAP.AccessAsUser.All   (IMAP read/write)
    - https://outlook.office.com/SMTP.Send               (outbound send)
    - offline_access                                     (refresh token)
    - openid / profile / email                           (user info)
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
import structlog
from sqlalchemy import text

from apps.api.services.integration_manager import _decrypt, _encrypt

logger = structlog.get_logger()


# Microsoft endpoints — tenant-specific for single-tenant apps
_AUTHORIZE_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
_TOKEN_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

# Scopes — full URIs for Outlook resources, short names for OIDC
SCOPES = [
    "https://outlook.office.com/IMAP.AccessAsUser.All",
    "https://outlook.office.com/SMTP.Send",
    "offline_access",
    "openid",
    "profile",
    "email",
]


# ---------------------------------------------------------------------------
# Load app credentials from integration_providers
# ---------------------------------------------------------------------------


async def _load_app_credentials(db, org_id: str) -> dict:
    """Load client_id / client_secret / tenant_id / redirect_uri from DB."""
    result = await db.execute(text("""
        SELECT api_key_encrypted, api_secret_encrypted, extra_config
          FROM integration_providers
         WHERE organization_id = :org_id
           AND provider_key = 'microsoft_oauth_app'
           AND is_enabled = true
    """), {"org_id": str(org_id)})
    row = result.fetchone()
    if not row:
        raise RuntimeError(
            f"microsoft_oauth_app not configured for org {org_id}. "
            "Store credentials in integration_providers first."
        )

    client_id_enc, client_secret_enc, extra_cfg = row
    client_id = _decrypt(client_id_enc) if client_id_enc else None
    client_secret = _decrypt(client_secret_enc) if client_secret_enc else None

    if not client_id or not client_secret:
        raise RuntimeError("Microsoft OAuth credentials are missing or failed to decrypt")

    # extra_config is already a dict when returned from JSONB
    cfg = extra_cfg if isinstance(extra_cfg, dict) else json.loads(extra_cfg or "{}")
    tenant_id = cfg.get("tenant_id")
    redirect_uri = cfg.get("redirect_uri")

    if not tenant_id:
        raise RuntimeError("tenant_id missing from microsoft_oauth_app.extra_config")
    if not redirect_uri:
        raise RuntimeError("redirect_uri missing from microsoft_oauth_app.extra_config")

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id,
        "redirect_uri": redirect_uri,
    }


# ---------------------------------------------------------------------------
# build_auth_url
# ---------------------------------------------------------------------------


async def build_auth_url(db, org_id: str, email_hint: Optional[str] = None) -> dict:
    """Return the URL to redirect the user to for consent.

    Returns:
        {
            "url": "https://login.microsoftonline.com/...",
            "state": "<random state token>",
        }
    """
    creds = await _load_app_credentials(db, org_id)
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": creds["client_id"],
        "response_type": "code",
        "redirect_uri": creds["redirect_uri"],
        "response_mode": "query",
        "scope": " ".join(SCOPES),
        "state": state,
        "prompt": "consent",  # force the consent screen — ensures refresh_token
    }
    if email_hint:
        params["login_hint"] = email_hint

    url = _AUTHORIZE_URL_TMPL.format(tenant=creds["tenant_id"]) + "?" + urlencode(params)
    return {"url": url, "state": state}


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


async def exchange_code(db, org_id: str, code: str) -> dict:
    """Exchange authorization code for tokens + user info.

    Returns:
        {
            "access_token": str,
            "refresh_token": str,
            "expires_at": datetime (UTC),
            "email": str,         # from id_token
            "display_name": str,
        }
    """
    creds = await _load_app_credentials(db, org_id)
    token_url = _TOKEN_URL_TMPL.format(tenant=creds["tenant_id"])

    data = {
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "code": code,
        "redirect_uri": creds["redirect_uri"],
        "grant_type": "authorization_code",
        "scope": " ".join(SCOPES),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            logger.error(
                "microsoft_oauth.exchange_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        tok = resp.json()

        # Fetch user email via Graph
        access_token = tok["access_token"]
        email, display_name = await _fetch_user_profile(client, access_token)

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tok.get("expires_in", 3600)))

    logger.info(
        "microsoft_oauth.exchange_ok",
        has_refresh=bool(tok.get("refresh_token")),
        email=email,
    )

    return {
        "access_token": access_token,
        "refresh_token": tok.get("refresh_token", ""),
        "expires_at": expires_at,
        "email": email,
        "display_name": display_name,
    }


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------


async def refresh_access_token(db, org_id: str, refresh_token: str) -> dict:
    """Use a refresh_token to get a new access_token.

    Returns:
        {
            "access_token": str,
            "refresh_token": str,  # may be rotated
            "expires_at": datetime (UTC),
        }
    """
    creds = await _load_app_credentials(db, org_id)
    token_url = _TOKEN_URL_TMPL.format(tenant=creds["tenant_id"])

    data = {
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(SCOPES),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            logger.error(
                "microsoft_oauth.refresh_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        tok = resp.json()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tok.get("expires_in", 3600)))
    new_refresh = tok.get("refresh_token", refresh_token)  # M365 usually rotates

    logger.info("microsoft_oauth.refresh_ok", rotated=(new_refresh != refresh_token))

    return {
        "access_token": tok["access_token"],
        "refresh_token": new_refresh,
        "expires_at": expires_at,
    }


# ---------------------------------------------------------------------------
# ensure_valid_token — refresh if expired, persist to InboxConnection
# ---------------------------------------------------------------------------


async def ensure_valid_token(db, inbox_connection) -> str:
    """Return a valid access token for the inbox; refresh if expired.

    Updates InboxConnection in-place and flushes (caller must commit).
    """
    now = datetime.now(timezone.utc)
    buffer = timedelta(minutes=5)

    # Still valid?
    if (
        inbox_connection.oauth_access_token_encrypted
        and inbox_connection.oauth_token_expires_at
        and inbox_connection.oauth_token_expires_at > now + buffer
    ):
        return _decrypt(inbox_connection.oauth_access_token_encrypted)

    # Need to refresh
    if not inbox_connection.oauth_refresh_token_encrypted:
        raise RuntimeError(
            f"InboxConnection {inbox_connection.id} has no refresh_token — user must re-consent"
        )

    refresh_token = _decrypt(inbox_connection.oauth_refresh_token_encrypted)
    result = await refresh_access_token(db, str(inbox_connection.org_id), refresh_token)

    inbox_connection.oauth_access_token_encrypted = _encrypt(result["access_token"])
    inbox_connection.oauth_refresh_token_encrypted = _encrypt(result["refresh_token"])
    inbox_connection.oauth_token_expires_at = result["expires_at"]
    inbox_connection.status = "active"
    inbox_connection.last_error = None
    await db.flush()

    return result["access_token"]


# ---------------------------------------------------------------------------
# Internal: user profile lookup
# ---------------------------------------------------------------------------


async def _fetch_user_profile(client: httpx.AsyncClient, access_token: str) -> tuple[str, str]:
    """Fetch the signed-in user's email + displayName via Graph."""
    try:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            email = data.get("mail") or data.get("userPrincipalName") or ""
            display_name = data.get("displayName") or ""
            return email, display_name
    except Exception as exc:
        logger.warning("microsoft_oauth.profile_fetch_failed", error=str(exc))
    return "", ""
