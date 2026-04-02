"""Opportunity-Cost Ranking Service — gather state, rank, persist."""
from __future__ import annotations
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.content import ContentItem
from packages.db.models.promote_winner import ActiveExperiment, PWExperimentWinner
from packages.db.models.quality_governor import QualityBlock
from packages.db.models.opportunity_cost import (
    CostOfDelayModel, OpportunityCostReport, RankedAction,
)
from packages.scoring.opportunity_cost_engine import (
    build_report, generate_candidates, rank_actions,
    score_cost_of_delay,
)


async def recompute_ranking(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(CostOfDelayModel).where(CostOfDelayModel.brand_id == brand_id))
    await db.execute(delete(RankedAction).where(RankedAction.brand_id == brand_id))
    await db.execute(delete(OpportunityCostReport).where(OpportunityCostReport.brand_id == brand_id))

    system_state = await _gather_system_state(db, brand_id)
    candidates = generate_candidates(system_state)
    ranked = rank_actions(candidates)
    report_data = build_report(ranked)

    report = OpportunityCostReport(
        brand_id=brand_id,
        total_actions=report_data["total_actions"],
        top_action_type=report_data["top_action_type"],
        total_opportunity_cost=report_data["total_opportunity_cost"],
        safe_to_wait_count=report_data["safe_to_wait_count"],
        summary=report_data["summary"],
    )
    db.add(report)
    await db.flush()

    for r in ranked:
        tid = None
        if r.get("target_id"):
            try:
                tid = uuid.UUID(str(r["target_id"]))
            except (ValueError, TypeError):
                pass

        db.add(RankedAction(
            brand_id=brand_id, report_id=report.id,
            action_type=r["action_type"], action_key=r["action_key"], target_id=tid,
            expected_upside=r["expected_upside"], cost_of_delay=r["cost_of_delay"],
            urgency=r["urgency"], confidence=r["confidence"],
            composite_rank=r["composite_rank"], rank_position=r["rank_position"],
            safe_to_wait=r["safe_to_wait"], explanation=r["explanation"],
        ))

        delay = r.get("delay_info", {})
        if delay:
            db.add(CostOfDelayModel(
                brand_id=brand_id, action_type=r["action_type"], action_key=r["action_key"],
                daily_cost=delay.get("daily_cost", 0), weekly_cost=delay.get("weekly_cost", 0),
                decay_rate=delay.get("decay_rate", 0), time_sensitivity=delay.get("time_sensitivity", "normal"),
                explanation=r.get("explanation"),
            ))

    await db.flush()
    return {"rows_processed": len(ranked), "status": "completed"}


async def _gather_system_state(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    state: dict[str, Any] = {"accounts": [], "experiment_winners": [], "blockers": [], "pending_experiments": [], "ready_assets": []}

    acct_reports = list((await db.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True))
    )).scalars().all())
    for r in acct_reports:
        state["accounts"].append({"id": str(r.account_id), "name": str(r.account_id)[:8], "state": r.current_state})

    winners = list((await db.execute(
        select(PWExperimentWinner).where(PWExperimentWinner.brand_id == brand_id, PWExperimentWinner.promoted.is_(False))
    )).scalars().all())
    for w in winners:
        state["experiment_winners"].append({"id": str(w.id), "name": str(w.variant_id)[:8], "confidence": float(w.confidence)})

    blocks = list((await db.execute(
        select(QualityBlock).where(QualityBlock.brand_id == brand_id, QualityBlock.is_active.is_(True)).limit(10)
    )).scalars().all())
    for b in blocks:
        state["blockers"].append({"id": str(b.id), "name": b.block_reason[:30]})

    pending_exps = list((await db.execute(
        select(ActiveExperiment).where(ActiveExperiment.brand_id == brand_id, ActiveExperiment.status == "active").limit(5)
    )).scalars().all())
    for e in pending_exps:
        state["pending_experiments"].append({"id": str(e.id), "name": e.experiment_name})

    ready = list((await db.execute(
        select(ContentItem).where(ContentItem.brand_id == brand_id, ContentItem.status.in_(("approved", "media_complete"))).limit(10)
    )).scalars().all())
    for ci in ready:
        state["ready_assets"].append({"id": str(ci.id), "title": ci.title or ""})

    return state


async def list_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(OpportunityCostReport).where(OpportunityCostReport.brand_id == brand_id).order_by(OpportunityCostReport.created_at.desc()).limit(10)
    )).scalars().all())


async def list_ranked_actions(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(RankedAction).where(RankedAction.brand_id == brand_id, RankedAction.is_active.is_(True)).order_by(RankedAction.rank_position)
    )).scalars().all())


async def get_top_actions(db: AsyncSession, brand_id: uuid.UUID, limit: int = 5) -> list[dict[str, Any]]:
    """Downstream: top N actions for copilot/commander consumption."""
    rows = list((await db.execute(
        select(RankedAction).where(RankedAction.brand_id == brand_id, RankedAction.is_active.is_(True)).order_by(RankedAction.rank_position).limit(limit)
    )).scalars().all())
    return [{"rank": r.rank_position, "type": r.action_type, "key": r.action_key, "upside": r.expected_upside, "delay_cost": r.cost_of_delay, "urgency": r.urgency, "safe_to_wait": r.safe_to_wait, "explanation": r.explanation} for r in rows]
