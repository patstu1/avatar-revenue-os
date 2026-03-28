"""Authentication endpoints — register, login, me."""
from fastapi import APIRouter, HTTPException, status

from apps.api.config import get_settings
from apps.api.deps import CurrentUser, DBSession, create_access_token
from apps.api.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from apps.api.services.auth_service import authenticate_user, register_user
from apps.api.services.audit_service import log_action

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DBSession):
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
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession):
    settings = get_settings()
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user.id, settings)
    await log_action(
        db,
        "user.logged_in",
        organization_id=user.organization_id,
        user_id=user.id,
        actor_type="human",
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return current_user
