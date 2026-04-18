"""Shared FastAPI dependencies: database sessions, auth, RBAC, org-scope, settings."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import Settings, get_settings
from packages.db.enums import UserRole
from packages.db.models.core import Brand, User
from packages.db.session import get_async_session_factory

logger = structlog.get_logger()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_async_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DBSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.api_secret_key, algorithm=settings.algorithm)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBSession,
    settings: SettingsDep,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.api_secret_key, algorithms=[settings.algorithm])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class RequireRole:
    """RBAC dependency. Usage: Depends(RequireRole(UserRole.ADMIN))
    Hierarchy: ADMIN > OPERATOR > VIEWER
    """

    HIERARCHY = {UserRole.ADMIN: 3, UserRole.OPERATOR: 2, UserRole.VIEWER: 1}

    def __init__(self, minimum_role: UserRole):
        self.minimum_role = minimum_role

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        """Use explicit User + Depends(get_current_user) here — not CurrentUser — so FastAPI
        does not nest Annotated types inside RequireRole (breaks dependency resolution in 0.115+)."""
        user_level = self.HIERARCHY.get(current_user.role, 0)
        required_level = self.HIERARCHY.get(self.minimum_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {self.minimum_role.value} role or higher",
            )
        return current_user


AdminUser = Annotated[User, Depends(RequireRole(UserRole.ADMIN))]
OperatorUser = Annotated[User, Depends(RequireRole(UserRole.OPERATOR))]
ViewerUser = Annotated[User, Depends(RequireRole(UserRole.VIEWER))]


async def require_brand_access(
    brand_id: uuid.UUID, user: User, db: AsyncSession
) -> Brand:
    """Shared org-scope safety helper.

    Verifies the brand exists and belongs to the user's organization.
    Use this in any router that accepts brand_id to prevent cross-org data leaks.

    Raises HTTPException 403 if the brand is not accessible.
    Returns the Brand ORM object if access is granted.
    """
    brand = (
        await db.execute(select(Brand).where(Brand.id == brand_id))
    ).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        logger.warning(
            "org_scope.access_denied",
            brand_id=str(brand_id),
            user_id=str(user.id),
            org_id=str(user.organization_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brand not accessible",
        )
    return brand
