"""Failure-Family Suppression workers — with auto kill-ledger population."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)

# Failure count threshold: when a family hits this, auto-create a KillLedgerEntry
KILL_THRESHOLD = 5


async def _auto_populate_kill_ledger(db, brand_id: uuid.UUID) -> int:
    """Auto-create KillLedgerEntry rows from failure families that exceed threshold.

    This closes the gap where failure patterns are detected but the kill ledger
    (which blocks future content generation) stays empty.
    """
    from packages.db.models.failure_family import FailureFamilyReport
    from packages.db.models.kill_ledger import KillLedgerEntry

    # Find failure families that exceed the threshold
    families = (await db.execute(
        select(FailureFamilyReport).where(
            FailureFamilyReport.brand_id == brand_id,
            FailureFamilyReport.failure_count >= KILL_THRESHOLD,
        )
    )).scalars().all()

    created = 0
    for fam in families:
        # Check if a kill entry already exists for this family
        existing = (await db.execute(
            select(KillLedgerEntry).where(
                KillLedgerEntry.brand_id == brand_id,
                KillLedgerEntry.killed_entity_type == fam.family_type,
                KillLedgerEntry.killed_entity_key == fam.family_key,
                KillLedgerEntry.is_active.is_(True),
            )
        )).scalar_one_or_none()

        if existing:
            continue

        entry = KillLedgerEntry(
            brand_id=brand_id,
            killed_entity_type=fam.family_type,
            killed_entity_key=fam.family_key,
            kill_reason=f"Auto-killed: {fam.failure_count} failures in family "
                        f"'{fam.family_key}' ({fam.family_type})",
            kill_source="failure_family_worker",
            failure_count=fam.failure_count,
            is_active=True,
        )
        db.add(entry)
        created += 1
        logger.info(
            "kill_ledger.auto_created family_type=%s family_key=%s failures=%d brand=%s",
            fam.family_type, fam.family_key, fam.failure_count, brand_id,
        )

    if created:
        await db.flush()
    return created


async def _run():
    from apps.api.services.failure_family_service import recompute_failure_families, run_decay_check

    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())

    count = 0
    total_kills = 0
    for bid in brands:
        try:
            async with get_async_session_factory()() as db:
                await recompute_failure_families(db, bid)
                await run_decay_check(db, bid)

                # Auto-populate kill ledger from high-failure families
                kills = await _auto_populate_kill_ledger(db, bid)
                total_kills += kills

                await db.commit()
                count += 1
        except Exception:
            logger.exception("failure family suppression failed for brand %s", bid)

    return count, total_kills


@shared_task(name="workers.failure_family_worker.tasks.recompute_failure_families", base=TrackedTask)
def recompute_failure_families_task():
    count, kills = run_async(_run())
    return {"status": "completed", "brands_processed": count, "kill_entries_created": kills}
