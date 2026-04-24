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

_async_engine = None
_async_session_factory = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("API_ENV") == "development",
            pool_size=_POOL_SIZE,
            max_overflow=_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_timeout=30,
            pool_recycle=300,
        )
    return _async_engine


def get_async_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


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


def run_async(coro):
    """Run an async coroutine safely from a Celery prefork worker.

    Celery's prefork pool reuses OS processes. asyncio.run() creates a new
    event loop per call, but SQLAlchemy's async engine caches connections
    bound to the previous loop. This causes 'Future attached to a different
    loop' errors on the second task execution in the same process.

    Fix: dispose the cached engine before creating a new loop. The engine
    is lazily recreated by get_async_engine() on the next use.

    Every Celery worker task that calls async code MUST use this function
    instead of bare asyncio.run().
    """
    import asyncio

    global _async_engine, _async_session_factory
    if _async_engine is not None:
        try:
            _async_engine.sync_engine.dispose()
        except Exception:
            pass
        _async_engine = None
        _async_session_factory = None

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def __getattr__(name: str):
    """Lazy module-level attribute access (PEP 562) for backward compatibility."""
    if name == "async_engine":
        return get_async_engine()
    if name in ("async_session_factory", "AsyncSessionLocal"):
        return get_async_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
