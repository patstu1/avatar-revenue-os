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

Send path:
    send_via_xoauth2_smtp(inbox_connection, to_email, subject, body_*)
    uses the access token against smtp.office365.com:587 with XOAUTH2.
    No new scopes needed beyond SMTP.Send (already granted above).
"""
from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode

import aiosmtplib
import httpx
import structlog
from sqlalchemy import text

from apps.api.services.integration_manager import _decrypt, _encrypt

logger = structlog.get_logger()


# Microsoft endpoints — tenant-specific for single-tenant apps
_AUTHORIZE_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
_TOKEN_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

# Scopes — we need two different Microsoft resources:
#   - outlook.office.com → IMAP (and SMTP, if the tenant allows it)
#   - graph.microsoft.com → Mail.Send (the ONLY way to send when the tenant
#     disables SmtpClientAuthentication, which is now the Microsoft default)
#
# Microsoft issues one token per resource. Our refresh_token is multi-resource,
# so during refresh we can mint either an outlook.office.com token (for IMAP)
# or a graph.microsoft.com token (for Mail.Send) depending on the scope we
# request.
OUTLOOK_IMAP_SCOPE = "https://outlook.office.com/IMAP.AccessAsUser.All"
OUTLOOK_SMTP_SCOPE = "https://outlook.office.com/SMTP.Send"
GRAPH_MAIL_SEND_SCOPE = "https://graph.microsoft.com/Mail.Send"

# Scopes requested at initial consent — includes both Outlook (IMAP/SMTP) and
# Graph (Mail.Send). User sees both in the consent screen, consents once, we
# can then refresh either token on-demand.
SCOPES = [
    OUTLOOK_IMAP_SCOPE,
    OUTLOOK_SMTP_SCOPE,
    GRAPH_MAIL_SEND_SCOPE,
    "offline_access",
    "openid",
    "profile",
    "email",
]

# Scope set used when refreshing to get an IMAP/SMTP token (outlook.office.com)
IMAP_REFRESH_SCOPES = [OUTLOOK_IMAP_SCOPE, OUTLOOK_SMTP_SCOPE, "offline_access"]

# Scope set used when refreshing to get a Graph token (graph.microsoft.com)
GRAPH_REFRESH_SCOPES = [GRAPH_MAIL_SEND_SCOPE, "offline_access"]


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


async def build_auth_url(db, org_id: str, email_hint: str | None = None) -> dict:
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

    Microsoft's v2.0 endpoint only allows scopes from a SINGLE resource in
    a token request (AADSTS28000). The authorize URL can include scopes
    from multiple resources (user sees all in the consent screen) but the
    code→token exchange must request scopes from one resource only.

    We request outlook.office.com scopes (IMAP + SMTP). The refresh_token
    Microsoft returns is multi-resource — it can later mint Graph tokens
    via get_graph_access_token for Mail.Send, assuming the user consented
    to Graph Mail.Send in the authorize step.

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
        # Single-resource only — outlook.office.com scopes
        "scope": " ".join(IMAP_REFRESH_SCOPES),
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
    """Use a refresh_token to get a new access_token for outlook.office.com.

    Same single-resource constraint as exchange_code — this path is for
    IMAP/SMTP (outlook.office.com). For Graph tokens, use
    get_graph_access_token which issues a refresh with GRAPH_REFRESH_SCOPES.

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
        # Single-resource: outlook.office.com (IMAP + SMTP)
        "scope": " ".join(IMAP_REFRESH_SCOPES),
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


# ---------------------------------------------------------------------------
# XOAUTH2 SMTP send — uses the existing SMTP.Send token against M365 SMTP
# NOTE: disabled by default in most M365 tenants (SmtpClientAuthentication
# off). Keep as a fallback path for tenants that re-enable it; primary
# send path is Microsoft Graph (see send_via_graph_sendmail below).
# ---------------------------------------------------------------------------


SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def _build_xoauth2_token(username: str, access_token: str) -> str:
    """Build the base64-encoded XOAUTH2 auth string per RFC 7628.

    Format: base64("user={email}\\x01auth=Bearer {token}\\x01\\x01")
    """
    raw = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


# ---------------------------------------------------------------------------
# Graph Mail.Send path — the primary send path (works on locked-down tenants)
# ---------------------------------------------------------------------------


async def get_graph_access_token(db, inbox_connection) -> str:
    """Mint a graph.microsoft.com-scoped access token from the inbox's
    multi-resource refresh token.

    Uses the refresh_token grant with GRAPH_REFRESH_SCOPES. The outlook.office.com
    token cached on the InboxConnection is untouched — this path is separate.
    We deliberately do NOT cache the Graph token on the row right now because
    the existing oauth_access_token_encrypted column is reserved for the IMAP
    (outlook.office.com) token. A production version would add a dedicated
    cache column; for now we mint fresh for every send (≤ one Graph call per
    reply sent).

    Raises RuntimeError if the refresh flow returns AADSTS65001 (user has
    not consented to Graph scopes) — caller should trigger re-consent.
    """
    if not inbox_connection.oauth_refresh_token_encrypted:
        raise RuntimeError(
            f"InboxConnection {inbox_connection.id} has no refresh_token"
        )
    refresh_token = _decrypt(inbox_connection.oauth_refresh_token_encrypted)

    creds = await _load_app_credentials(db, str(inbox_connection.org_id))
    token_url = _TOKEN_URL_TMPL.format(tenant=creds["tenant_id"])

    data = {
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(GRAPH_REFRESH_SCOPES),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            body = resp.text
            logger.error(
                "microsoft_oauth.graph_token_failed",
                status=resp.status_code,
                body=body[:500],
            )
            if "AADSTS65001" in body:
                raise RuntimeError(
                    "M365 consent missing for Graph Mail.Send — the user "
                    "must re-authorize the ProofHook Mail Sync app to add "
                    "the new Graph scope. Generate a fresh authorize URL "
                    "from microsoft_oauth.build_auth_url and have them "
                    "click it."
                )
            raise RuntimeError(f"graph token refresh failed: {resp.status_code} {body[:200]}")
        tok = resp.json()

    # If Microsoft rotated the refresh_token, persist it so IMAP path keeps
    # working too. Multi-resource refresh tokens rotate together.
    new_refresh = tok.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        inbox_connection.oauth_refresh_token_encrypted = _encrypt(new_refresh)
        await db.flush()
        logger.info(
            "microsoft_oauth.refresh_token_rotated",
            inbox_id=str(inbox_connection.id),
            via="graph",
        )

    return tok["access_token"]


async def send_via_graph_sendmail(
    db,
    inbox_connection,
    *,
    to_email: str,
    subject: str,
    body_text: str = "",
    body_html: str = "",
    reply_to: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    save_to_sent_items: bool = True,
) -> dict:
    """Send mail via Microsoft Graph POST /me/sendMail.

    Returns:
        {
            "success": bool,
            "error": Optional[str],
            "message_id": Optional[str],  # Graph doesn't return one; we
                                          # synthesize a pseudo-id
            "provider": "m365_graph_sendmail",
        }
    """
    try:
        access_token = await get_graph_access_token(db, inbox_connection)
    except Exception as exc:
        return {
            "success": False,
            "error": f"graph token unavailable: {exc}",
            "message_id": None,
            "provider": "m365_graph_sendmail",
        }

    # Build the Graph message payload
    # Graph sendMail uses HTML by default; we always send HTML + a plain fallback.
    content_type = "HTML" if body_html else "Text"
    content = body_html if body_html else (body_text or "")

    message: dict = {
        "subject": subject,
        "body": {
            "contentType": content_type,
            "content": content,
        },
        "toRecipients": [
            {"emailAddress": {"address": to_email}},
        ],
    }
    if reply_to:
        message["replyTo"] = [{"emailAddress": {"address": reply_to}}]
    # Internet headers for threading
    internet_headers = []
    if in_reply_to:
        internet_headers.append({"name": "x-ph-in-reply-to", "value": in_reply_to})
    if references:
        internet_headers.append({"name": "x-ph-references", "value": references[:996]})
    if internet_headers:
        message["internetMessageHeaders"] = internet_headers

    payload = {"message": message, "saveToSentItems": save_to_sent_items}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{GRAPH_API_BASE}/me/sendMail",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as exc:
            logger.error("microsoft_oauth.graph_send_exception", error=str(exc))
            return {
                "success": False,
                "error": f"graph network error: {exc}",
                "message_id": None,
                "provider": "m365_graph_sendmail",
            }

    # Graph sendMail returns 202 Accepted on success with no body
    if resp.status_code == 202:
        synthetic_id = f"<graph-send-{datetime.now(timezone.utc).timestamp()}@{inbox_connection.email_address}>"
        logger.info(
            "microsoft_oauth.graph_send_ok",
            mailbox=inbox_connection.email_address,
            to=to_email,
            subject=subject,
        )
        return {
            "success": True,
            "error": None,
            "message_id": synthetic_id,
            "provider": "m365_graph_sendmail",
        }

    body = resp.text[:500] if resp.text else ""
    logger.error(
        "microsoft_oauth.graph_send_failed",
        status=resp.status_code,
        body=body,
        mailbox=inbox_connection.email_address,
    )
    return {
        "success": False,
        "error": f"graph sendMail {resp.status_code}: {body[:200]}",
        "message_id": None,
        "provider": "m365_graph_sendmail",
    }


async def send_via_xoauth2_smtp(
    db,
    inbox_connection,
    *,
    to_email: str,
    subject: str,
    body_text: str = "",
    body_html: str = "",
    reply_to: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> dict:
    """Send an email via smtp.office365.com using XOAUTH2 with the mailbox's
    OAuth access token.

    Refreshes the token on InboxConnection in-place if expired. Caller must
    commit the session afterward if you care about persisting any rotated
    refresh token.

    Returns:
        {
            "success": bool,
            "error": Optional[str],
            "message_id": Optional[str],
            "provider": "m365_xoauth2_smtp",
        }
    """
    username = inbox_connection.email_address
    try:
        access_token = await ensure_valid_token(db, inbox_connection)
    except Exception as exc:
        logger.error(
            "microsoft_oauth.smtp_token_fetch_failed",
            email=username,
            error=str(exc),
        )
        return {
            "success": False,
            "error": f"token refresh failed: {exc}",
            "message_id": None,
            "provider": "m365_xoauth2_smtp",
        }

    # Build MIME message
    msg = MIMEMultipart("alternative")
    display = inbox_connection.display_name or ""
    msg["From"] = f"{display} <{username}>" if display else username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = reply_to or username
    msg["List-Unsubscribe"] = f"<mailto:{username}?subject=unsubscribe>"
    msg["X-Mailer"] = "ProofHook"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    plain = body_text
    if not plain and body_html:
        import re as _re
        plain = _re.sub(r"<[^>]+>", "", body_html).strip()
    if plain:
        msg.attach(MIMEText(plain, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    if not plain and not body_html:
        msg.attach(MIMEText("", "plain", "utf-8"))

    # Open SMTP connection + STARTTLS
    smtp = aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT, start_tls=False)
    try:
        await smtp.connect()
        await smtp.ehlo()
        await smtp.starttls()
        await smtp.ehlo()

        # Manual AUTH XOAUTH2 (aiosmtplib doesn't ship a built-in helper)
        xoauth2_token = _build_xoauth2_token(username, access_token)
        code, response = await smtp.execute_command(
            b"AUTH", b"XOAUTH2", xoauth2_token.encode("ascii")
        )
        if code not in (235,):
            # If the server returned 334, it's asking for a continuation —
            # an empty line means "I don't have more info", and the server
            # will then return the real error code.
            if code == 334:
                code, response = await smtp.execute_command(b"")
            if code != 235:
                raise aiosmtplib.SMTPAuthenticationError(code, response)

        # Send message
        errors, rcpt_msg = await smtp.send_message(msg)
        await smtp.quit()

        message_id = msg.get("Message-ID") or f"<xoauth2-{datetime.now(timezone.utc).timestamp()}>"
        logger.info(
            "microsoft_oauth.smtp_sent",
            to=to_email,
            subject=subject,
            message_id=message_id,
            mailbox=username,
        )
        return {
            "success": True,
            "error": None,
            "message_id": message_id,
            "provider": "m365_xoauth2_smtp",
        }
    except aiosmtplib.SMTPAuthenticationError as exc:
        try:
            await smtp.quit()
        except Exception:
            pass
        logger.error(
            "microsoft_oauth.smtp_auth_failed",
            mailbox=username,
            code=getattr(exc, "code", None),
            error=str(exc),
        )
        return {
            "success": False,
            "error": f"XOAUTH2 auth failed: {exc}",
            "message_id": None,
            "provider": "m365_xoauth2_smtp",
        }
    except aiosmtplib.SMTPException as exc:
        try:
            await smtp.quit()
        except Exception:
            pass
        logger.error(
            "microsoft_oauth.smtp_send_failed",
            mailbox=username,
            error=str(exc),
        )
        return {
            "success": False,
            "error": f"SMTP error: {exc}",
            "message_id": None,
            "provider": "m365_xoauth2_smtp",
        }
    except Exception as exc:
        try:
            await smtp.quit()
        except Exception:
            pass
        logger.error(
            "microsoft_oauth.smtp_unexpected",
            mailbox=username,
            error=str(exc),
            exc_info=True,
        )
        return {
            "success": False,
            "error": f"unexpected: {exc}",
            "message_id": None,
            "provider": "m365_xoauth2_smtp",
        }
