"""Autonomy Policy — manages brand-level auto-approval grants.

Two entry points:
  1. check_autonomy_grant(db, brand_id, action_type) — called by revenue_execution
     at action creation time. If a grant exists, promotes ASSISTED → AUTONOMOUS.
  2. update_autonomy_grants(db) — called hourly by Celery Beat. Evaluates all
     (brand, action_type) pairs and creates/updates/revokes grants based on history.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.autonomy_grants import BrandAutonomyGrant
from packages.db.models.core import Brand
from packages.db.models.system_events import OperatorAction

logger = structlog.get_logger()

# --- Grant criteria ---
# Tier 1: ≥10 completed, ≥85% success → daily_cap=5
# Tier 2: ≥20 completed, ≥95% success → daily_cap=20
MIN_COMPLETED_FOR_GRANT = 10
MIN_SUCCESS_RATE_TIER1 = 0.85
MIN_SUCCESS_COUNT_TIER1 = 8
MIN_SUCCESS_RATE_TIER2 = 0.95
MIN_SUCCESS_COUNT_TIER2 = 20

# Revocation threshold: success_rate drops below 0.7 → revoke
REVOCATION_THRESHOLD = 0.70

# History window
HISTORY_DAYS = 30


async def check_autonomy_grant(
    db: AsyncSession, brand_id: uuid.UUID, action_type: str,
) -> BrandAutonomyGrant | None:
    """Check if a brand has an active grant for this action type.

    If the grant exists and the daily cap is not exhausted, increments
    today_count and returns the grant. The caller should promote the
    action from ASSISTED to AUTONOMOUS.

    Returns None if no active grant exists or the cap is hit.
    """
    grant = (await db.execute(
        select(BrandAutonomyGrant).where(
            BrandAutonomyGrant.brand_id == brand_id,
            BrandAutonomyGrant.action_type == action_type,
            BrandAutonomyGrant.revoked_at.is_(None),
        )
    )).scalar_one_or_none()

    if not grant:
        return None

    today = date.today()

    # Daily reset
    if grant.last_reset_date < today:
        grant.today_count = 0
        grant.last_reset_date = today

    # Cap check
    if grant.today_count >= grant.daily_cap:
        return None

    # Increment and return
    grant.today_count += 1
    await db.flush()
    return grant


async def update_all_autonomy_grants(db: AsyncSession) -> dict:
    """Evaluate all (brand, action_type) pairs and create/update/revoke grants.

    Called hourly. For each combination with enough completed assisted actions:
    - If success rate qualifies → upsert a grant
    - If success rate dropped → revoke existing grant
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)

    # Get all active brands
    brands = (await db.execute(
        select(Brand.id).where(Brand.is_active.is_(True))
    )).scalars().all()

    grants_created = 0
    grants_upgraded = 0
    grants_revoked = 0

    for brand_id in brands:
        # Get action_type stats for this brand in the history window
        stats = (await db.execute(
            select(
                OperatorAction.action_type,
                func.count(OperatorAction.id).label("total"),
                func.count(OperatorAction.id).filter(
                    OperatorAction.outcome_score > 0
                ).label("succeeded"),
            ).where(
                OperatorAction.brand_id == brand_id,
                OperatorAction.status == "completed",
                OperatorAction.completed_at >= cutoff,
            ).group_by(OperatorAction.action_type)
        )).all()

        for action_type, total, succeeded in stats:
            if total < MIN_COMPLETED_FOR_GRANT:
                continue

            success_rate = succeeded / total if total > 0 else 0.0

            # Check for existing grant
            existing = (await db.execute(
                select(BrandAutonomyGrant).where(
                    BrandAutonomyGrant.brand_id == brand_id,
                    BrandAutonomyGrant.action_type == action_type,
                )
            )).scalar_one_or_none()

            # --- Revocation check ---
            if existing and existing.revoked_at is None and success_rate < REVOCATION_THRESHOLD:
                existing.revoked_at = datetime.now(timezone.utc)
                existing.revoke_reason = f"success_rate_dropped to {success_rate:.2f}"
                grants_revoked += 1
                continue

            # --- Grant/upgrade check ---
            if success_rate >= MIN_SUCCESS_RATE_TIER2 and succeeded >= MIN_SUCCESS_COUNT_TIER2:
                daily_cap = 20
            elif success_rate >= MIN_SUCCESS_RATE_TIER1 and succeeded >= MIN_SUCCESS_COUNT_TIER1:
                daily_cap = 5
            else:
                continue

            if existing and existing.revoked_at is None:
                # Update existing grant
                if existing.daily_cap < daily_cap:
                    existing.daily_cap = daily_cap
                    grants_upgraded += 1
                existing.success_count = succeeded
                existing.success_rate = success_rate
            elif existing and existing.revoked_at is not None:
                # Re-grant after revocation if criteria met again
                existing.revoked_at = None
                existing.revoke_reason = None
                existing.daily_cap = daily_cap
                existing.success_count = succeeded
                existing.success_rate = success_rate
                existing.granted_at = datetime.now(timezone.utc)
                existing.granted_by = "auto"
                grants_created += 1
            else:
                # New grant
                db.add(BrandAutonomyGrant(
                    brand_id=brand_id,
                    action_type=action_type,
                    granted_by="auto",
                    success_count=succeeded,
                    success_rate=success_rate,
                    daily_cap=daily_cap,
                ))
                grants_created += 1

    await db.flush()
    return {
        "brands_evaluated": len(brands),
        "grants_created": grants_created,
        "grants_upgraded": grants_upgraded,
        "grants_revoked": grants_revoked,
    }
