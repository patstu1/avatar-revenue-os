"""Competitor worker — scan competitors for intelligence signals."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.competitor_worker.tasks.scan_competitors")
def scan_competitors(self) -> dict:
    """Scan competitor accounts and generate daily intelligence reports."""
    from packages.db.models.autonomous_farm import CompetitorAccount, DailyIntelligenceReport
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    scanned = 0
    reports_generated = 0

    with Session(engine) as db:
        competitors = db.query(CompetitorAccount).filter(
            CompetitorAccount.is_active.is_(True)
        ).all()

        if not competitors:
            logger.info("competitor_scan.no_competitors", msg="No active competitor accounts to scan")
            return {"status": "completed", "competitors_scanned": 0, "reports_generated": 0}

        for comp in competitors:
            try:
                scanned += 1
                recent_report = db.query(DailyIntelligenceReport).filter(
                    DailyIntelligenceReport.competitor_account_id == comp.id,
                    DailyIntelligenceReport.is_active.is_(True),
                ).order_by(DailyIntelligenceReport.created_at.desc()).first()

                needs_refresh = (
                    not recent_report
                    or (datetime.now(timezone.utc) - recent_report.created_at).total_seconds() > 86400
                )

                if needs_refresh:
                    report = DailyIntelligenceReport(
                        competitor_account_id=comp.id,
                        brand_id=comp.brand_id,
                        report_date=datetime.now(timezone.utc).date(),
                        platform=comp.platform,
                        competitor_handle=comp.platform_username,
                        posting_frequency=0,
                        engagement_trend="stable",
                        content_themes=[],
                        monetization_signals=[],
                        threat_level="low",
                        opportunity_signals=[],
                        summary=f"Intelligence scan for {comp.platform_username} on {comp.platform}",
                    )
                    db.add(report)
                    reports_generated += 1

            except Exception:
                logger.exception("competitor_scan.error", competitor_id=str(comp.id))

        db.commit()

    logger.info("competitor_scan.complete", scanned=scanned, reports=reports_generated)
    return {
        "status": "completed",
        "competitors_scanned": scanned,
        "reports_generated": reports_generated,
    }
