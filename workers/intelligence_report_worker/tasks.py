"""Intelligence report worker — generate daily operational summary."""
from __future__ import annotations

import logging

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.intelligence_report_worker.tasks.generate_daily_report")
def generate_daily_report(self) -> dict:
    """Gather last-24h metrics and produce an intelligence report."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from packages.db.models.content import ContentItem
    from packages.db.models.publishing import PerformanceMetric
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    with Session(engine) as session:
        try:
            total_created = session.execute(
                select(func.count())
                .select_from(ContentItem)
                .where(ContentItem.created_at >= cutoff)
            ).scalar() or 0

            total_approved = session.execute(
                select(func.count())
                .select_from(ContentItem)
                .where(
                    ContentItem.created_at >= cutoff,
                    ContentItem.status == "approved",
                )
            ).scalar() or 0

            total_published = session.execute(
                select(func.count())
                .select_from(ContentItem)
                .where(
                    ContentItem.created_at >= cutoff,
                    ContentItem.status == "published",
                )
            ).scalar() or 0

            revenue_sum = session.execute(
                select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0))
                .where(PerformanceMetric.measured_at >= cutoff)
            ).scalar() or 0.0

        except Exception:
            logger.exception("Error gathering intelligence report data")
            return {"status": "error", "message": "failed to gather report data"}

    forecast_data = {}
    try:
        from packages.scoring.revenue_forecast_engine import forecast_revenue, generate_forecast_summary
        daily_revenues = [
            float(r[0]) for r in session.execute(
                select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0))
                .where(PerformanceMetric.measured_at >= datetime.now(timezone.utc) - timedelta(days=30))
                .group_by(func.date(PerformanceMetric.measured_at))
                .order_by(func.date(PerformanceMetric.measured_at))
            ).all()
        ]
        if daily_revenues and len(daily_revenues) >= 7:
            from packages.db.models.accounts import CreatorAccount
            active_accounts = session.execute(
                select(func.count()).select_from(CreatorAccount).where(CreatorAccount.is_active.is_(True))
            ).scalar() or 0
            forecast = forecast_revenue(daily_revenues, accounts_active=active_accounts)
            forecast_data = {
                "forecast_30d": forecast["forecast_revenue_30d"],
                "forecast_low": forecast["forecast_low"],
                "forecast_high": forecast["forecast_high"],
                "trend_direction": forecast["trend_direction"],
                "confidence": forecast["confidence"],
                "summary": generate_forecast_summary(forecast),
            }
    except Exception:
        logger.warning("Revenue forecast generation failed — insufficient data or error")

    report = {
        "period": "last_24h",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content_created": total_created,
        "content_approved": total_approved,
        "content_published": total_published,
        "revenue_summary": round(float(revenue_sum), 2),
        "revenue_forecast": forecast_data,
    }

    logger.info(
        "Daily intelligence report: created=%d approved=%d published=%d revenue=%.2f forecast=%s",
        total_created, total_approved, total_published, float(revenue_sum),
        forecast_data.get("summary", "no forecast"),
    )

    return {"status": "completed", "report": report}
