"""Account-State Intelligence Service — classify, persist, transition, act."""
from __future__ import annotations
import uuid
from typing import Any
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.account_state_intel import (
    AccountStateAction, AccountStateReport, AccountStateTransition,
)
from packages.db.models.content import ContentItem
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.account_state_intel_engine import (
    classify_account_state,
    detect_transition,
    generate_actions,
)


async def recompute_account_states(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict[str, Any]:
    accounts = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all())

    old_reports = {}
    for r in (await db.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True))
    )).scalars().all():
        old_reports[r.account_id] = r.current_state

    await db.execute(delete(AccountStateAction).where(AccountStateAction.brand_id == brand_id))
    await db.execute(delete(AccountStateReport).where(AccountStateReport.brand_id == brand_id))

    processed = 0
    for acct in accounts:
        inputs = await _gather_inputs(db, acct)
        result = classify_account_state(inputs)

        report = AccountStateReport(
            brand_id=brand_id,
            account_id=acct.id,
            current_state=result["current_state"],
            confidence=result["confidence"],
            next_best_move=result["next_best_move"],
            blocked_actions=result["blocked_actions"],
            suitable_content_forms=result["suitable_content_forms"],
            monetization_intensity=result["monetization_intensity"],
            posting_cadence=result["posting_cadence"],
            expansion_eligible=result["expansion_eligible"],
            explanation=result["explanation"],
            inputs_json=inputs,
        )
        db.add(report)
        await db.flush()

        prev_state = old_reports.get(acct.id, "newborn")
        transition = detect_transition(prev_state, result["current_state"], inputs)
        if transition:
            db.add(AccountStateTransition(
                brand_id=brand_id,
                account_id=acct.id,
                from_state=transition["from_state"],
                to_state=transition["to_state"],
                trigger=transition["trigger"],
                confidence=result["confidence"],
            ))

        actions = generate_actions(result["current_state"], inputs)
        for a in actions:
            db.add(AccountStateAction(
                brand_id=brand_id,
                account_id=acct.id,
                report_id=report.id,
                action_type=a["action_type"],
                action_detail=a.get("action_detail"),
                priority=a.get("priority", "medium"),
            ))

        processed += 1

    await db.flush()
    return {"rows_processed": processed, "status": "completed"}


async def _gather_inputs(db: AsyncSession, acct: CreatorAccount) -> dict[str, Any]:
    health_val = acct.account_health.value if hasattr(acct.account_health, "value") else str(acct.account_health)

    age_days = (datetime.now(timezone.utc) - acct.created_at.replace(tzinfo=timezone.utc)).days if acct.created_at else 0

    post_count = (await db.execute(
        select(func.count()).select_from(ContentItem).where(ContentItem.creator_account_id == acct.id)
    )).scalar() or 0

    perf_agg = (await db.execute(
        select(
            func.sum(PerformanceMetric.impressions).label("impressions"),
            func.avg(PerformanceMetric.engagement_rate).label("engagement_rate"),
        ).where(PerformanceMetric.creator_account_id == acct.id)
    )).one_or_none()
    impressions = float(perf_agg.impressions or 0) if perf_agg else 0
    engagement_rate = float(perf_agg.engagement_rate or 0) if perf_agg else 0

    return {
        "age_days": age_days,
        "post_count": post_count,
        "impressions": impressions,
        "engagement_rate": engagement_rate,
        "conversion_rate": float(acct.conversion_rate or 0),
        "fatigue_score": float(acct.fatigue_score or 0),
        "saturation_score": float(acct.saturation_score or 0),
        "account_health": health_val,
        "total_revenue": float(acct.total_revenue or 0),
        "total_profit": float(acct.total_profit or 0),
        "blocker_state": "",
    }


async def list_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True)).order_by(AccountStateReport.current_state)
    )).scalars().all())


async def list_transitions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(AccountStateTransition).where(AccountStateTransition.brand_id == brand_id).order_by(AccountStateTransition.created_at.desc()).limit(50)
    )).scalars().all())


async def list_actions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(AccountStateAction).where(AccountStateAction.brand_id == brand_id, AccountStateAction.is_active.is_(True)).order_by(AccountStateAction.priority)
    )).scalars().all())


async def get_state_for_account(db: AsyncSession, account_id: uuid.UUID) -> dict[str, Any]:
    """Downstream query: return current state + policy for an account."""
    report = (await db.execute(
        select(AccountStateReport).where(AccountStateReport.account_id == account_id, AccountStateReport.is_active.is_(True)).order_by(AccountStateReport.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not report:
        return {"current_state": "newborn", "monetization_intensity": "none", "posting_cadence": "slow", "expansion_eligible": False, "suitable_content_forms": ["short_video", "text_post"], "blocked_actions": ["aggressive_monetization"]}
    return {
        "current_state": report.current_state,
        "monetization_intensity": report.monetization_intensity,
        "posting_cadence": report.posting_cadence,
        "expansion_eligible": report.expansion_eligible,
        "suitable_content_forms": report.suitable_content_forms or [],
        "blocked_actions": report.blocked_actions or [],
    }
