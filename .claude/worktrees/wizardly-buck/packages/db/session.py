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

_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "3"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "2"))

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
            pool_reset_on_return="rollback",  # kill idle-in-transaction on return
        )
    return _async_engine


class _AutoRollbackSession(AsyncSession):
    """AsyncSession subclass that auto-rollbacks on close.

    Prevents 'idle in transaction' leaks when workers use asyncio.run()
    and the event loop dies before the pool can reset the connection.
    """

    async def close(self) -> None:
        if self.in_transaction():
            await self.rollback()
        await super().close()


def get_async_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(),
            class_=_AutoRollbackSession,
            expire_on_commit=False,
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
        pool_reset_on_return="rollback",  # kill idle-in-transaction on return
    )


# ---------------------------------------------------------------------------
# Persistent worker event loop — one loop per process, reused across tasks.
# This avoids the "Future attached to a different loop" crash that happens
# when asyncio.run() creates/destroys a loop each time while asyncpg
# connections are tied to the old loop.
# ---------------------------------------------------------------------------
_worker_loop = None


def _get_worker_loop():
    """Get or create a persistent event loop for Celery worker tasks."""
    import asyncio
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop


def worker_async_run(coro):
    """Run an async coroutine from a sync Celery worker.

    Uses a persistent event loop so asyncpg connections stay valid across
    task invocations. The _AutoRollbackSession ensures transactions are
    rolled back when sessions close, and pool_reset_on_return="rollback"
    handles any that slip through.

    Usage in a Celery task::

        from packages.db.session import worker_async_run

        @shared_task
        def my_task():
            return worker_async_run(_my_async_impl())
    """
    loop = _get_worker_loop()
    return loop.run_until_complete(coro)


def __getattr__(name: str):
    """Lazy module-level attribute access (PEP 562) for backward compatibility."""
    if name == "async_engine":
        return get_async_engine()
    if name in ("async_session_factory", "AsyncSessionLocal"):
        return get_async_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
