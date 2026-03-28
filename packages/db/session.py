import os
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://avataros:avataros_dev_2026@localhost:5433/avatar_revenue_os")
DATABASE_URL_SYNC = os.getenv("DATABASE_URL_SYNC", "postgresql://avataros:avataros_dev_2026@localhost:5433/avatar_revenue_os")

async_engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("API_ENV") == "development",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
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


def get_sync_engine():
    return create_engine(DATABASE_URL_SYNC, echo=False, pool_pre_ping=True)
