"""Health check endpoints — liveness, readiness, and deep checks."""
from redis.asyncio import Redis as AsyncRedis
from fastapi import APIRouter
from sqlalchemy import text

from apps.api.config import get_settings
from apps.api.deps import DBSession

router = APIRouter()


@router.get("/healthz")
async def healthz():
    """Liveness probe — confirms the process is running."""
    return {"status": "ok", "service": "avatar-revenue-os-api"}


@router.get("/readyz")
async def readyz(db: DBSession):
    """Readiness probe — checks Postgres and Redis connectivity."""
    checks: dict[str, bool] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    try:
        settings = get_settings()
        r = AsyncRedis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    try:
        settings = get_settings()
        r_celery = AsyncRedis.from_url(settings.celery_broker_url, socket_connect_timeout=2)
        await r_celery.ping()
        await r_celery.aclose()
        checks["celery_broker"] = True
    except Exception:
        checks["celery_broker"] = False

    all_ok = all(checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }
