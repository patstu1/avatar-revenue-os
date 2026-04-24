"""Celery tasks for Autonomous Execution Phase D — agents, revenue pressure, blockers, escalations."""

from __future__ import annotations

import structlog
from celery import shared_task
from sqlalchemy import select

from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = structlog.get_logger()


async def _active_brand_ids() -> list:
    async with get_async_session_factory()() as session:
        rows = (await session.execute(select(Brand.id).where(Brand.is_active.is_(True)))).scalars().all()
        return list(rows)


@shared_task(name="workers.autonomous_phase_d_worker.tasks.run_agent_orchestration", base=TrackedTask)
def run_agent_orchestration():
    """Run a full agent orchestration cycle for every active brand."""
    from apps.api.services import autonomous_phase_d_service as svc

    async def _inner():
        brand_ids = await _active_brand_ids()
        for bid in brand_ids:
            try:
                async with get_async_session_factory()() as session:
                    result = await svc.recompute_agent_orchestration(session, bid)
                    await session.commit()
                    logger.info("phase_d.agent_orchestration.done", brand_id=str(bid), **result)
            except Exception:
                logger.exception("phase_d.agent_orchestration.error", brand_id=str(bid))

    run_async(_inner())


@shared_task(name="workers.autonomous_phase_d_worker.tasks.run_revenue_pressure", base=TrackedTask)
def run_revenue_pressure():
    """Recompute revenue pressure for every active brand."""
    from apps.api.services import autonomous_phase_d_service as svc

    async def _inner():
        brand_ids = await _active_brand_ids()
        for bid in brand_ids:
            try:
                async with get_async_session_factory()() as session:
                    result = await svc.recompute_revenue_pressure(session, bid)
                    await session.commit()
                    logger.info("phase_d.revenue_pressure.done", brand_id=str(bid), **result)
            except Exception:
                logger.exception("phase_d.revenue_pressure.error", brand_id=str(bid))

    run_async(_inner())


@shared_task(name="workers.autonomous_phase_d_worker.tasks.run_blocker_detection", base=TrackedTask)
def run_blocker_detection():
    """Detect blockers across all active brands."""
    from apps.api.services import autonomous_phase_d_service as svc

    async def _inner():
        brand_ids = await _active_brand_ids()
        for bid in brand_ids:
            try:
                async with get_async_session_factory()() as session:
                    result = await svc.recompute_blocker_detection(session, bid)
                    await session.commit()
                    logger.info("phase_d.blocker_detection.done", brand_id=str(bid), **result)
            except Exception:
                logger.exception("phase_d.blocker_detection.error", brand_id=str(bid))

    run_async(_inner())


@shared_task(name="workers.autonomous_phase_d_worker.tasks.run_escalation_generation", base=TrackedTask)
def run_escalation_generation():
    """Generate operator escalations from blockers + revenue pressure."""
    from apps.api.services import autonomous_phase_d_service as svc

    async def _inner():
        brand_ids = await _active_brand_ids()
        for bid in brand_ids:
            try:
                async with get_async_session_factory()() as session:
                    result = await svc.recompute_escalations(session, bid)
                    await session.commit()
                    logger.info("phase_d.escalation_generation.done", brand_id=str(bid), **result)
            except Exception:
                logger.exception("phase_d.escalation_generation.error", brand_id=str(bid))

    run_async(_inner())
