"""Data Pruning Worker — clean up old metrics, stale records, and unbounded tables."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from celery import shared_task
from sqlalchemy import delete, select

from workers.base_task import TrackedTask

from packages.db.session import async_session_factory, run_async

logger = logging.getLogger(__name__)

METRICS_RETENTION_DAYS = 90
FLEET_REPORT_RETENTION_DAYS = 30
DAILY_REPORT_RETENTION_DAYS = 60


async def _prune():
    results = {"metrics_deleted": 0, "fleet_reports_deleted": 0, "daily_reports_deleted": 0}
    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            from packages.db.models.publishing import PerformanceMetric
            cutoff = now - timedelta(days=METRICS_RETENTION_DAYS)
            r = await db.execute(delete(PerformanceMetric).where(PerformanceMetric.measured_at < cutoff))
            results["metrics_deleted"] = r.rowcount or 0
        except Exception:
            logger.exception("Failed to prune PerformanceMetric")

        try:
            from packages.db.models.autonomous_farm import FleetStatusReport
            cutoff = now - timedelta(days=FLEET_REPORT_RETENTION_DAYS)
            r = await db.execute(delete(FleetStatusReport).where(FleetStatusReport.created_at < cutoff))
            results["fleet_reports_deleted"] = r.rowcount or 0
        except Exception:
            logger.exception("Failed to prune FleetStatusReport")

        try:
            from packages.db.models.autonomous_farm import DailyIntelligenceReport
            cutoff_date = (now - timedelta(days=DAILY_REPORT_RETENTION_DAYS)).strftime("%Y-%m-%d")
            r = await db.execute(delete(DailyIntelligenceReport).where(DailyIntelligenceReport.report_date < cutoff_date))
            results["daily_reports_deleted"] = r.rowcount or 0
        except Exception:
            logger.exception("Failed to prune DailyIntelligenceReport")

        await db.commit()

    total = sum(results.values())
    if total > 0:
        logger.info("Data pruning complete: %s", results)
    return results


@shared_task(name="workers.data_pruning_worker.tasks.prune_stale_data", base=TrackedTask)
def prune_stale_data():
    return run_async(_prune())
