"""Authentication endpoints — register, login, me, password reset."""
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from apps.api.config import get_settings
from apps.api.deps import CurrentUser, DBSession, create_access_token
from apps.api.rate_limit import auth_rate_limit
from apps.api.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from apps.api.services.audit_service import log_action
from apps.api.services.auth_service import authenticate_user, hash_password, register_user, verify_password
from packages.db.models.core import User

router = APIRouter()
logger = structlog.get_logger()

# Password reset token TTL (1 hour)
RESET_TOKEN_TTL_SECONDS = 3600


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DBSession, request: Request, _=Depends(auth_rate_limit)):
    try:
        user = await register_user(
            db,
            organization_name=body.organization_name,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await log_action(
        db,
        "user.registered",
        organization_id=user.organization_id,
        user_id=user.id,
        actor_type="human",
        entity_type="user",
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession, request: Request, _=Depends(auth_rate_limit)):
    settings = get_settings()
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        logger.warning("auth.login.failed", email=body.email, ip=request.client.host if request.client else None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user.id, settings)
    await log_action(
        db,
        "user.logged_in",
        organization_id=user.organization_id,
        user_id=user.id,
        actor_type="human",
        ip_address=request.client.host if request.client else None,
    )
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: CurrentUser, db: DBSession):
    """Issue a fresh access token for an authenticated user.

    The current 24h stateless JWT model means operators working long sessions
    would be forcibly logged out. This endpoint lets the frontend silently
    refresh before expiry without re-entering credentials.

    The current token must still be valid — this is NOT a refresh-token grant.
    It is a re-issue: present a valid access token, get a new one with a fresh
    expiry window. This avoids adding a second token type and the complexity of
    token rotation/revocation lists while still preventing mid-session logouts.
    """
    settings = get_settings()
    token = create_access_token(current_user.id, settings)
    await log_action(
        db,
        "user.token_refreshed",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_type="human",
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return current_user


# ── Password Reset ──────────────────────────────────────────────────────
# Flow:
#   1. User hits /auth/forgot-password with their email
#   2. We generate a random token, store it on the user record with expiry
#   3. We email a reset link to the user via SMTP (same SendGrid config)
#   4. User clicks link, lands on frontend page with token in URL
#   5. Frontend calls /auth/reset-password with token + new password
#   6. We validate, hash the new password, clear the token
#
# Token storage: user.password_reset_token (hashed) + user.password_reset_expires_at
# We always return 200 from /forgot-password to prevent email enumeration.


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: PasswordResetRequest, db: DBSession, request: Request,
    _=Depends(auth_rate_limit),
):
    """Request a password reset email.

    Always returns 200 to prevent email enumeration. If the email exists,
    a reset link is sent via SMTP. Token expires in 1 hour.
    """
    # Look up user by email (case-insensitive)
    user = (await db.execute(
        select(User).where(User.email.ilike(body.email))
    )).scalar_one_or_none()

    if user and user.is_active:
        # Generate a URL-safe random token (43 chars)
        raw_token = secrets.token_urlsafe(32)
        # Store a hash of the token so a DB leak doesn't expose reset tokens
        import hashlib
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        user.password_reset_token = token_hash
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(seconds=RESET_TOKEN_TTL_SECONDS)
        await db.flush()

        # Send reset email via the SMTP integration
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            from apps.api.services.integration_manager import get_credential_full

            creds = await get_credential_full(db, user.organization_id, "smtp")
            extra = creds.get("extra_config") or {}
            host = extra.get("host", "")
            port = int(extra.get("port", 587))
            username = extra.get("username", "")
            password = creds.get("api_key", "")
            from_email = extra.get("from_email", "") or username

            settings = get_settings()
            frontend_url = (settings.api_cors_origins[0] if settings.api_cors_origins else "").rstrip("/")
            if not frontend_url:
                frontend_url = "https://app.nvironments.com"
            reset_link = f"{frontend_url}/reset-password?token={raw_token}"

            if host and username and password:
                msg = MIMEMultipart("alternative")
                msg["From"] = f"Avatar Revenue OS <{from_email}>"
                msg["To"] = user.email
                msg["Subject"] = "Password reset — Avatar Revenue OS"
                msg.attach(MIMEText(
                    f"A password reset was requested for your account.\n\n"
                    f"Click here to reset your password (expires in 1 hour):\n"
                    f"{reset_link}\n\n"
                    f"If you did not request this, ignore this email — your password will remain unchanged.",
                    "plain",
                ))
                await aiosmtplib.send(
                    msg, hostname=host, port=port,
                    username=username, password=password, start_tls=True,
                )
                logger.info("auth.password_reset_sent", email=user.email)
            else:
                logger.warning("auth.password_reset_smtp_missing", email=user.email)
        except Exception as e:
            logger.exception("auth.password_reset_send_failed", email=user.email, error=str(e))

        await log_action(
            db, "user.password_reset_requested",
            organization_id=user.organization_id,
            user_id=user.id,
            actor_type="human",
            ip_address=request.client.host if request.client else None,
        )

    # Always return success to prevent email enumeration
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    body: PasswordResetConfirm, db: DBSession, request: Request,
    _=Depends(auth_rate_limit),
):
    """Complete a password reset using the emailed token."""
    import hashlib
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()

    user = (await db.execute(
        select(User).where(User.password_reset_token == token_hash)
    )).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if not user.password_reset_expires_at or user.password_reset_expires_at < datetime.now(timezone.utc):
        # Token expired — clear it
        user.password_reset_token = None
        user.password_reset_expires_at = None
        await db.flush()
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    # Set the new password and clear the reset token
    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    await db.flush()

    await log_action(
        db, "user.password_reset_completed",
        organization_id=user.organization_id,
        user_id=user.id,
        actor_type="human",
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Password has been reset. You can now log in with your new password."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    body: PasswordChangeRequest, current_user: CurrentUser, db: DBSession,
    request: Request, _=Depends(auth_rate_limit),
):
    """Change password for a logged-in user. Requires current password."""
    # Re-fetch user to get hashed_password (current_user is a response model)
    user = (await db.execute(
        select(User).where(User.id == current_user.id)
    )).scalar_one_or_none()

    if not user or not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = hash_password(body.new_password)
    await db.flush()

    await log_action(
        db, "user.password_changed",
        organization_id=user.organization_id,
        user_id=user.id,
        actor_type="human",
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Password changed successfully."}
