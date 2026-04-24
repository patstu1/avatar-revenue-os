"""Microsoft 365 inbox OAuth flow — connect mailbox for IMAP/SMTP sync.

Endpoints:
    GET  /oauth/microsoft/connect?org_id=...&email_hint=...
         → Redirect to Microsoft consent screen
    GET  /oauth/callback/microsoft?code=...&state=...
         → Exchange code, create/update InboxConnection, redirect to success page

These endpoints are PUBLIC (no auth required) because the operator needs to complete
the OAuth flow in a browser. State token in the URL binds the session.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from apps.api.deps import DBSession
from apps.api.services.integration_manager import _encrypt
from packages.clients.microsoft_oauth import build_auth_url, exchange_code
from packages.db.models.email_pipeline import InboxConnection

logger = structlog.get_logger()

router = APIRouter()

# In-memory state store — maps state token to {org_id, email_hint, created_at}
# Acceptable for single-operator use; swap for Redis if multi-user.
_inbox_oauth_state: dict[str, dict] = {}


@router.get("/oauth/microsoft/connect")
async def microsoft_connect(
    db: DBSession,
    org_id: uuid.UUID = Query(..., description="Organization ID that will own the inbox"),
    email_hint: str | None = Query(None, description="Pre-fill the login email"),
):
    """Generate a state token and redirect to Microsoft consent screen."""
    try:
        auth_data = await build_auth_url(db, str(org_id), email_hint=email_hint)
    except Exception as exc:
        logger.error("microsoft_connect.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to build auth URL: {exc}")

    _inbox_oauth_state[auth_data["state"]] = {
        "org_id": str(org_id),
        "email_hint": email_hint,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("microsoft_connect.redirecting", org_id=str(org_id), email_hint=email_hint)
    return RedirectResponse(url=auth_data["url"], status_code=302)


@router.get("/oauth/callback/microsoft")
async def microsoft_callback(
    db: DBSession,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    """Handle Microsoft's redirect after user consent — exchange code, store tokens."""
    if error:
        logger.error("microsoft_callback.error", error=error, description=error_description)
        return HTMLResponse(
            _error_page(f"Microsoft returned error: {error}<br/>{error_description or ''}"),
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse(_error_page("Missing code or state parameter"), status_code=400)

    state_data = _inbox_oauth_state.pop(state, None)
    if not state_data:
        return HTMLResponse(
            _error_page("Invalid or expired state token — please restart the flow"),
            status_code=400,
        )

    org_id = state_data["org_id"]

    # Exchange code for tokens
    try:
        result = await exchange_code(db, org_id, code)
    except Exception as exc:
        logger.error("microsoft_callback.exchange_failed", error=str(exc))
        return HTMLResponse(_error_page(f"Token exchange failed: {exc}"), status_code=500)

    email = result["email"] or state_data.get("email_hint") or "unknown@proofhook.com"
    display_name = result["display_name"] or email

    # Upsert InboxConnection
    existing = (await db.execute(
        select(InboxConnection).where(
            InboxConnection.org_id == uuid.UUID(org_id),
            InboxConnection.email_address == email,
        )
    )).scalar_one_or_none()

    if existing:
        existing.display_name = display_name
        existing.provider = "outlook_imap"
        existing.host = "outlook.office365.com"
        existing.port = 993
        existing.auth_method = "xoauth2"
        existing.credential_provider_key = "microsoft_oauth_app"
        existing.oauth_access_token_encrypted = _encrypt(result["access_token"])
        existing.oauth_refresh_token_encrypted = _encrypt(result["refresh_token"])
        existing.oauth_token_expires_at = result["expires_at"]
        existing.status = "active"
        existing.is_active = True
        existing.last_error = None
        existing.consecutive_failures = 0
        inbox = existing
        logger.info("microsoft_callback.updated_inbox", inbox_id=str(inbox.id), email=email)
    else:
        inbox = InboxConnection(
            org_id=uuid.UUID(org_id),
            email_address=email,
            display_name=display_name,
            provider="outlook_imap",
            host="outlook.office365.com",
            port=993,
            auth_method="xoauth2",
            credential_provider_key="microsoft_oauth_app",
            oauth_access_token_encrypted=_encrypt(result["access_token"]),
            oauth_refresh_token_encrypted=_encrypt(result["refresh_token"]),
            oauth_token_expires_at=result["expires_at"],
            status="active",
            is_active=True,
        )
        db.add(inbox)
        await db.flush()
        logger.info("microsoft_callback.created_inbox", inbox_id=str(inbox.id), email=email)

    await db.commit()

    return HTMLResponse(_success_page(email, str(inbox.id)))


def _success_page(email: str, inbox_id: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<title>Inbox Connected</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 560px; margin: 80px auto; padding: 24px; color: #111; }}
  .ok {{ background: #0f7a2e; color: white; padding: 4px 10px; border-radius: 4px; font-size: 14px; display: inline-block; }}
  h1 {{ font-size: 28px; margin: 16px 0 8px; }}
  .email {{ font-family: ui-monospace, monospace; background: #f4f4f5; padding: 8px 12px; border-radius: 4px; }}
  .meta {{ color: #666; font-size: 14px; margin-top: 16px; }}
</style>
</head>
<body>
  <div class="ok">✓ Connected</div>
  <h1>Inbox connected successfully.</h1>
  <p>Mailbox: <span class="email">{email}</span></p>
  <p>ProofHook will now sync incoming mail, classify replies, and draft responses automatically.</p>
  <div class="meta">Inbox ID: {inbox_id}<br/>You can close this window.</div>
</body>
</html>"""


def _error_page(message: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<title>Connection Failed</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 560px; margin: 80px auto; padding: 24px; color: #111; }}
  .err {{ background: #b91c1c; color: white; padding: 4px 10px; border-radius: 4px; font-size: 14px; display: inline-block; }}
  h1 {{ font-size: 28px; margin: 16px 0 8px; }}
  pre {{ background: #f4f4f5; padding: 12px; border-radius: 4px; white-space: pre-wrap; font-size: 13px; }}
</style>
</head>
<body>
  <div class="err">✗ Failed</div>
  <h1>Could not connect inbox.</h1>
  <pre>{message}</pre>
</body>
</html>"""
