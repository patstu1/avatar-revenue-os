"""Brain Architecture Phase A — recurring Celery tasks."""
from __future__ import annotations

import asyncio
import uuid

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand
from packages.db.session import async_session_factory
from workers.base_task import BaseTask

logger = structlog.get_logger()


async def _all_brand_ids(db: AsyncSession) -> list[uuid.UUID]:
    result = await db.execute(select(Brand.id).where(Brand.is_active.is_(True)))
    return [r[0] for r in result.all()]


async def _consolidate_memory():
    from apps.api.services import brain_phase_a_service as svc

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_brain_memory(db, bid)
                await db.commit()
                logger.info("brain.memory_consolidated", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.memory_consolidation_failed", brand_id=str(bid))


async def _recompute_account_states():
    from apps.api.services import brain_phase_a_service as svc

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_account_states(db, bid)
                await db.commit()
                logger.info("brain.account_states_recomputed", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.account_state_failed", brand_id=str(bid))


async def _recompute_opportunity_states():
    from apps.api.services import brain_phase_a_service as svc

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_opportunity_states(db, bid)
                await db.commit()
                logger.info("brain.opportunity_states_recomputed", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.opportunity_state_failed", brand_id=str(bid))


async def _recompute_execution_states():
    from apps.api.services import brain_phase_a_service as svc

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_execution_states(db, bid)
                await db.commit()
                logger.info("brain.execution_states_recomputed", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.execution_state_failed", brand_id=str(bid))


async def _recompute_audience_states():
    from apps.api.services import brain_phase_a_service as svc

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_audience_states_v2(db, bid)
                await db.commit()
                logger.info("brain.audience_states_recomputed", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.audience_state_failed", brand_id=str(bid))


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.consolidate_brain_memory")
def consolidate_brain_memory():
    asyncio.run(_consolidate_memory())


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.recompute_account_states")
def recompute_account_states():
    asyncio.run(_recompute_account_states())


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.recompute_opportunity_states")
def recompute_opportunity_states():
    asyncio.run(_recompute_opportunity_states())


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.recompute_execution_states")
def recompute_execution_states():
    asyncio.run(_recompute_execution_states())


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.recompute_audience_states")
def recompute_audience_states():
    asyncio.run(_recompute_audience_states())


# ── Brain Phase B tasks ───────────────────────────────────────────────

async def _recompute_brain_decisions():
    from apps.api.services import brain_phase_b_service as svc
    from apps.api.services.intelligence_bridge import surface_intelligence_actions
    from apps.api.services.action_dispatcher import dispatch_autonomous_actions

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)

    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_brain_decisions(db, bid)
                await db.commit()
                logger.info("brain.decisions_recomputed", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.decision_recompute_failed", brand_id=str(bid))

    # ── Bridge: convert fresh decisions into OperatorActions ──────────
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                brand = (await db.execute(
                    select(Brand).where(Brand.id == bid)
                )).scalar_one_or_none()
                if not brand or not brand.organization_id:
                    continue

                actions = await surface_intelligence_actions(
                    db, brand.organization_id, bid
                )
                await db.commit()
                if actions:
                    logger.info(
                        "brain.actions_surfaced",
                        brand_id=str(bid),
                        count=len(actions),
                    )
        except Exception:
            logger.exception("brain.action_surface_failed", brand_id=str(bid))

    # ── Dispatch: execute autonomous actions that meet confidence gate ─
    surfaced_orgs: set[uuid.UUID] = set()
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                brand = (await db.execute(
                    select(Brand).where(Brand.id == bid)
                )).scalar_one_or_none()
                if brand and brand.organization_id and brand.organization_id not in surfaced_orgs:
                    surfaced_orgs.add(brand.organization_id)
                    dispatch_result = await dispatch_autonomous_actions(
                        db, brand.organization_id
                    )
                    await db.commit()
                    logger.info(
                        "brain.autonomous_dispatch",
                        org_id=str(brand.organization_id),
                        **dispatch_result,
                    )
        except Exception:
            logger.exception("brain.autonomous_dispatch_failed", brand_id=str(bid))


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.recompute_brain_decisions")
def recompute_brain_decisions():
    asyncio.run(_recompute_brain_decisions())


# ── Brain Phase C tasks ───────────────────────────────────────────────

async def _recompute_agent_mesh():
    from apps.api.services import brain_phase_c_service as svc

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_agent_mesh(db, bid)
                await db.commit()
                logger.info("brain.agent_mesh_recomputed", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.agent_mesh_recompute_failed", brand_id=str(bid))


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.recompute_agent_mesh")
def recompute_agent_mesh():
    asyncio.run(_recompute_agent_mesh())


# ── Brain Phase D tasks ───────────────────────────────────────────────

async def _recompute_meta_monitoring():
    from apps.api.services import brain_phase_d_service as svc

    async with async_session_factory() as db:
        brand_ids = await _all_brand_ids(db)
    for bid in brand_ids:
        try:
            async with async_session_factory() as db:
                result = await svc.recompute_meta_monitoring(db, bid)
                await db.commit()
                logger.info("brain.meta_monitoring_recomputed", brand_id=str(bid), **result)
        except Exception:
            logger.exception("brain.meta_monitoring_recompute_failed", brand_id=str(bid))


@shared_task(base=BaseTask, name="workers.brain_worker.tasks.recompute_meta_monitoring")
def recompute_meta_monitoring():
    asyncio.run(_recompute_meta_monitoring())
