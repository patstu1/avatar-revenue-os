"""Health check endpoints."""
from fastapi import APIRouter
from sqlalchemy import text

from apps.api.deps import DBSession

router = APIRouter()


@router.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "avatar-revenue-os-api"}


@router.get("/readyz")
async def readyz(db: DBSession):
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    status = "ready" if db_ok else "degraded"
    return {"status": status, "checks": {"database": db_ok}}
