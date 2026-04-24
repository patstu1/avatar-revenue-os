"""Authentication service — registration, login, password hashing."""
from __future__ import annotations

import uuid

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import UserRole
from packages.db.models.core import Organization, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


async def register_user(
    db: AsyncSession,
    organization_name: str,
    email: str,
    password: str,
    full_name: str,
) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")

    slug = organization_name.lower().replace(" ", "-")
    org = Organization(name=organization_name, slug=slug)
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
