"""Promote-Winner workers — evaluate experiments, decay check, observation ingest."""
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.promote_winner import ActiveExperiment
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


async def _ingest_experiment_observations():
    """Auto-populate experiment observations from real performance metrics."""
    from packages.db.models.portfolio import PerformanceMetric
    from packages.db.models.promote_winner import PWExperimentObservation, PWExperimentVariant

    async with get_async_session_factory()() as db:
        experiments = list((await db.execute(
            select(ActiveExperiment).where(ActiveExperiment.status == "active")
        )).scalars().all())

        observations_created = 0
        for exp in experiments:
            variants = list((await db.execute(
                select(PWExperimentVariant).where(PWExperimentVariant.experiment_id == exp.id)
            )).scalars().all())

            for variant in variants:
                config = variant.variant_config or {}
                content_ids = config.get("content_item_ids", [])
                for cid_str in content_ids:
                    try:
                        import uuid
                        cid = uuid.UUID(cid_str)
                        metrics = list((await db.execute(
                            select(PerformanceMetric).where(PerformanceMetric.content_item_id == cid)
                        )).scalars().all())
                        for m in metrics:
                            existing = (await db.execute(
                                select(PWExperimentObservation).where(
                                    PWExperimentObservation.variant_id == variant.id,
                                    PWExperimentObservation.metric_name == "engagement_rate",
                                ).limit(1)
                            )).scalar_one_or_none()
                            if not existing:
                                db.add(PWExperimentObservation(
                                    experiment_id=exp.id, variant_id=variant.id,
                                    metric_name="engagement_rate", metric_value=float(m.engagement_rate or 0),
                                ))
                                db.add(PWExperimentObservation(
                                    experiment_id=exp.id, variant_id=variant.id,
                                    metric_name="impressions", metric_value=float(m.impressions or 0),
                                ))
                                if m.revenue and m.revenue > 0:
                                    db.add(PWExperimentObservation(
                                        experiment_id=exp.id, variant_id=variant.id,
                                        metric_name="revenue", metric_value=float(m.revenue),
                                    ))
                                observations_created += 1
                    except Exception:
                        logger.debug("observation ingestion failed for content %s", cid_str, exc_info=True)
        await db.commit()
        return observations_created


async def _evaluate_active():
    from apps.api.services.promote_winner_service import evaluate_experiment, run_decay_check

    obs_count = await _ingest_experiment_observations()
    logger.info("experiment observations ingested: %d", obs_count)

    async with get_async_session_factory()() as db:
        experiments = list((await db.execute(
            select(ActiveExperiment).where(ActiveExperiment.status == "active")
        )).scalars().all())
        evaluated = 0
        for exp in experiments:
            try:
                await evaluate_experiment(db, exp.id)
                evaluated += 1
            except Exception:
                logger.exception("evaluate failed for %s", exp.id)
        await db.commit()

    async with get_async_session_factory()() as db:
        brand_ids = list((await db.execute(
            select(ActiveExperiment.brand_id).distinct()
        )).scalars().all())
        for bid in brand_ids:
            try:
                await run_decay_check(db, bid)
            except Exception:
                logger.exception("decay check failed for brand %s", bid)
        await db.commit()

    return evaluated


@shared_task(name="workers.promote_winner_worker.tasks.evaluate_and_promote", base=TrackedTask)
def evaluate_and_promote():
    count = run_async(_evaluate_active())
    return {"status": "completed", "experiments_evaluated": count}
