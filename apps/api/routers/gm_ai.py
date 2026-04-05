"""GM AI API — The General Manager interface.

Strategic operating brain that scans, plans, directs, and manages
the entire revenue machine.
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Query
from apps.api.deps import CurrentUser, DBSession
from apps.api.services import gm_ai as gm

router = APIRouter()


@router.get("/gm/scan")
async def full_scan(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Phase 1: Full system scan — accounts, platforms, revenue, offers, patterns, sponsors, content."""
    return await gm.run_full_scan(db, brand_id)


@router.get("/gm/blueprint")
async def scale_blueprint(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Phase 2: Scale blueprint — platforms, accounts, archetypes, monetization timing, expansion triggers."""
    return await gm.generate_scale_blueprint(db, brand_id)


@router.get("/gm/directive")
async def operating_directive(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Phase 3: Current operating directive — what to do RIGHT NOW, ranked by impact."""
    return await gm.get_gm_directive(db, brand_id)


@router.get("/gm/status")
async def gm_status(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Quick status check — health, metrics, status line."""
    return await gm.get_gm_status(db, brand_id)
