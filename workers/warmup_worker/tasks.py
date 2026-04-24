"""Warmup worker — enforce warmup cadence and detect shadow bans across all accounts."""
from __future__ import annotations

import logging

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.warmup_worker.tasks.enforce_warmup_cadence")
def enforce_warmup_cadence(self) -> dict:
    """Check warmup phase and shadow-ban signals for every active CreatorAccount."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.enums import HealthStatus
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.publishing import PerformanceMetric
    from packages.db.session import get_sync_engine
    from packages.scoring.warmup_engine import detect_shadow_ban, determine_warmup_phase

    engine = get_sync_engine()
    accounts_checked = 0
    shadow_bans_detected = 0
    suppressed = 0

    with Session(engine) as session:
        accounts = session.execute(
            select(CreatorAccount).where(CreatorAccount.is_active.is_(True))
        ).scalars().all()

        for account in accounts:
            try:
                phase_info = determine_warmup_phase(account.created_at)
                logger.info(
                    "Account %s phase=%s age_days=%d",
                    account.id, phase_info["phase"], phase_info["age_days"],
                )

                recent_metrics = (
                    session.query(PerformanceMetric)
                    .filter(PerformanceMetric.creator_account_id == account.id)
                    .order_by(PerformanceMetric.measured_at.desc())
                    .limit(10)
                    .all()
                )
                metric_dicts = [
                    {"impressions": m.impressions or 0, "views": m.views or 0}
                    for m in recent_metrics
                ]

                ban_result = detect_shadow_ban(metric_dicts)
                if ban_result["detected"]:
                    shadow_bans_detected += 1
                    logger.warning(
                        "Shadow ban detected for account %s: %s",
                        account.id, ban_result["reason"],
                    )
                    if account.account_health != HealthStatus.SUSPENDED:
                        account.account_health = HealthStatus.SUSPENDED
                        suppressed += 1

                accounts_checked += 1
            except Exception:
                logger.exception("Error checking warmup for account %s", account.id)

        session.commit()

    return {
        "status": "completed",
        "accounts_checked": accounts_checked,
        "shadow_bans_detected": shadow_bans_detected,
        "accounts_suppressed": suppressed,
    }
