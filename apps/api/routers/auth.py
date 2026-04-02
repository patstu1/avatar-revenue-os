"""Authentication endpoints — register, login, me."""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.api.config import get_settings
from apps.api.deps import CurrentUser, DBSession, create_access_token
from apps.api.rate_limit import auth_rate_limit
from apps.api.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from apps.api.services.auth_service import authenticate_user, register_user
from apps.api.services.audit_service import log_action

router = APIRouter()
logger = structlog.get_logger()


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
