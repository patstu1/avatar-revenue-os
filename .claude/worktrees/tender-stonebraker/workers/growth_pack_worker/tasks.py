"""Scheduled growth pack recomputes — persists status via TrackedTask."""
import asyncio
import uuid

from workers.celery_app import app
from workers.base_task import TrackedTask
from packages.db.session import async_session_factory
from apps.api.services import growth_pack_service as gps
from apps.api.services import growth_commander_service as gcs
from sqlalchemy import select
from packages.db.models.core import Brand


async def _run_brand(brand_id: uuid.UUID) -> dict:
    async with async_session_factory() as db:
        await gcs.recompute_growth_commands(db, brand_id, user_id=None)
        await gps.recompute_portfolio_launch_plan(db, brand_id)
        await gps.recompute_account_blueprints(db, brand_id)
        await gps.recompute_platform_allocation(db, brand_id)
        await gps.recompute_niche_deployment(db, brand_id)
        await gps.recompute_growth_blockers_pack(db, brand_id)
        await gps.recompute_capital_deployment(db, brand_id)
        await gps.recompute_cross_account_cannibalization(db, brand_id)
        await gps.recompute_portfolio_output(db, brand_id)
        await db.commit()
    return {"brand_id": str(brand_id), "ok": True}


@app.task(base=TrackedTask, bind=True, name="workers.growth_pack_worker.tasks.recompute_all_growth_pack")
def recompute_all_growth_pack(self) -> dict:
    async def inner():
        async with async_session_factory() as db:
            r = await db.execute(select(Brand.id))
            brands = list(r.scalars().all())
        n = 0
        for bid in brands:
            await _run_brand(bid)
            n += 1
        return {"brands_processed": n}

    return asyncio.run(inner())


@app.task(base=TrackedTask, bind=True, name="workers.growth_pack_worker.tasks.recompute_brand_growth_pack")
def recompute_brand_growth_pack(self, brand_id: str) -> dict:
    return asyncio.run(_run_brand(uuid.UUID(brand_id)))
