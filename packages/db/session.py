import os
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _resolve_db_urls() -> tuple[str, str]:
    """Single source of truth for database URLs.

    Priority: environment variable > Settings (pydantic) > hardcoded default.
    """
    default_async = "postgresql+asyncpg://avataros:avataros_dev_2026@localhost:5433/avatar_revenue_os"
    default_sync = "postgresql://avataros:avataros_dev_2026@localhost:5433/avatar_revenue_os"
    env_async = os.getenv("DATABASE_URL")
    env_sync = os.getenv("DATABASE_URL_SYNC")
    if env_async and env_sync:
        return env_async, env_sync
    try:
        from apps.api.config import get_settings
        s = get_settings()
        return env_async or s.database_url, env_sync or s.database_url_sync
    except Exception:
        return env_async or default_async, env_sync or default_sync


DATABASE_URL, DATABASE_URL_SYNC = _resolve_db_urls()

_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))

async_engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("API_ENV") == "development",
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=300,
)

async_session_factory = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@lru_cache(maxsize=1)
def get_sync_engine():
    return create_engine(
        DATABASE_URL_SYNC,
        echo=False,
        pool_pre_ping=True,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        pool_recycle=300,
    )


AsyncSessionLocal = async_session_factory
