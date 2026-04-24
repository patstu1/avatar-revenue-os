"""Engagement Automation Worker — perform warmup engagement actions for seed/trickle accounts."""
from __future__ import annotations

import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.models.accounts import CreatorAccount
from packages.db.models.autonomous_farm import AccountWarmupPlan
from packages.db.session import get_async_session_factory, run_async
from packages.scoring.engagement_automation_engine import generate_engagement_plan
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


async def _run_engagement():
    """Find warmup accounts and generate engagement actions."""
    async with get_async_session_factory()() as db:
        warmup_accounts = list((await db.execute(
            select(AccountWarmupPlan).where(
                AccountWarmupPlan.current_phase.in_(["seed", "trickle"]),
                AccountWarmupPlan.is_active.is_(True),
            )
        )).scalars().all())

    plans_generated = 0
    for wp in warmup_accounts:
        try:
            acct = None
            async with get_async_session_factory()() as db:
                acct = (await db.execute(
                    select(CreatorAccount).where(CreatorAccount.id == wp.account_id)
                )).scalar_one_or_none()

            if not acct:
                continue

            platform = getattr(acct.platform, 'value', str(acct.platform)) if acct.platform else "youtube"
            niche = acct.niche_focus or "general"

            plan = generate_engagement_plan(wp.current_phase, platform, niche)
            if plan.get("actions"):
                logger.info(
                    "engagement_plan account=%s phase=%s actions=%d comments=%d",
                    wp.account_id, wp.current_phase,
                    len(plan["actions"]), len(plan.get("comments", [])),
                )
                plans_generated += 1
        except Exception:
            logger.exception("engagement plan failed for account %s", wp.account_id)

    return {"plans_generated": plans_generated, "warmup_accounts": len(warmup_accounts)}


@shared_task(name="workers.engagement_worker.tasks.run_engagement", base=TrackedTask)
def run_engagement():
    return run_async(_run_engagement())
