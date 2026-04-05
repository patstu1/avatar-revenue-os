"""Service Sales Engine — manages the service/consulting revenue pipeline.

Transforms from "records service revenue passively" to "qualifies leads,
tracks deal pipeline, surfaces follow-up actions, measures conversion."
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action
from packages.db.models.core import Brand
from packages.db.models.revenue_ledger import RevenueLedgerEntry
from packages.db.models.saas_metrics import HighTicketDeal

logger = structlog.get_logger()

DEAL_STAGES = ["awareness", "interest", "consideration", "proposal", "negotiation", "closed_won", "closed_lost"]


async def get_service_pipeline(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Full service/consulting pipeline: deals by stage, conversion, revenue."""
    stage_q = await db.execute(
        select(HighTicketDeal.stage, func.count(),
               func.sum(HighTicketDeal.deal_value),
               func.sum(HighTicketDeal.deal_value * HighTicketDeal.probability))
        .where(HighTicketDeal.brand_id == brand_id, HighTicketDeal.is_active.is_(True))
        .group_by(HighTicketDeal.stage)
    )
    by_stage = {}
    for row in stage_q.all():
        by_stage[str(row[0])] = {"count": row[1], "value": float(row[2] or 0),
                                   "weighted_value": float(row[3] or 0)}

    total_pipeline = sum(d["value"] for s, d in by_stage.items() if s not in ("closed_won", "closed_lost"))
    weighted_pipeline = sum(d["weighted_value"] for s, d in by_stage.items() if s not in ("closed_won", "closed_lost"))
    won = by_stage.get("closed_won", {})
    lost = by_stage.get("closed_lost", {})
    win_rate = won.get("count", 0) / (won.get("count", 0) + lost.get("count", 0)) if (won.get("count", 0) + lost.get("count", 0)) > 0 else 0

    # Service revenue from ledger
    svc_rev = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0))
        .where(RevenueLedgerEntry.brand_id == brand_id,
               RevenueLedgerEntry.revenue_source_type.in_(["service_fee", "consulting_fee"]),
               RevenueLedgerEntry.is_active.is_(True))
    )).scalar() or 0.0

    # Stalled deals
    stalled = (await db.execute(
        select(HighTicketDeal)
        .where(HighTicketDeal.brand_id == brand_id, HighTicketDeal.is_active.is_(True),
               HighTicketDeal.stage.notin_(["closed_won", "closed_lost"]),
               HighTicketDeal.updated_at < datetime.now(timezone.utc) - timedelta(days=14))
    )).scalars().all()

    return {
        "by_stage": by_stage,
        "total_pipeline_value": total_pipeline,
        "weighted_pipeline_value": weighted_pipeline,
        "win_rate": round(win_rate, 3),
        "total_service_revenue": float(svc_rev),
        "stalled_deals": [{"id": str(d.id), "customer": d.customer_name, "stage": d.stage,
                            "value": float(d.deal_value or 0)} for d in stalled],
        "stalled_count": len(stalled),
    }


async def qualify_leads(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    """Score and qualify service leads from the deal pipeline."""
    deals = (await db.execute(
        select(HighTicketDeal).where(
            HighTicketDeal.brand_id == brand_id, HighTicketDeal.is_active.is_(True),
            HighTicketDeal.stage.in_(["awareness", "interest", "consideration"]),
        )
    )).scalars().all()

    qualified = []
    for deal in deals:
        value = float(deal.deal_value or 0)
        prob = float(deal.probability or 0)
        interactions = deal.interactions or 0
        days_active = (datetime.now(timezone.utc) - deal.created_at).days if deal.created_at else 0

        qual_score = (
            0.30 * min(1.0, value / max(float(deal.deal_value or 1) * 2, 1)) +  # Relative to deal size, not fixed 10K
            0.25 * prob +
            0.25 * min(1.0, interactions / 10) +
            0.20 * min(1.0, days_active / 30)
        )

        qualification = "hot" if qual_score > 0.6 else "warm" if qual_score > 0.3 else "cold"

        qualified.append({
            "deal_id": str(deal.id),
            "customer": deal.customer_name,
            "stage": deal.stage,
            "value": value,
            "probability": prob,
            "qualification": qualification,
            "qual_score": round(qual_score, 3),
            "next_action": "send_proposal" if qualification == "hot" else "follow_up" if qualification == "warm" else "nurture",
        })

    qualified.sort(key=lambda x: x["qual_score"], reverse=True)
    return qualified


async def surface_service_actions(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID,
) -> list[dict]:
    """Create operator actions for service pipeline management."""
    pipeline = await get_service_pipeline(db, brand_id)
    leads = await qualify_leads(db, brand_id)
    created = []

    # Hot leads → proposal action
    for lead in leads:
        if lead["qualification"] == "hot":
            a = await emit_action(
                db, org_id=org_id, action_type="send_proposal",
                title=f"Hot lead: {lead['customer'][:40]} (${lead['value']:,.0f})",
                description=f"Stage: {lead['stage']}, score: {lead['qual_score']:.0%}. Send proposal.",
                category="monetization", priority="high",
                brand_id=brand_id, source_module="service_sales_engine",
                entity_type="high_ticket_deal", entity_id=uuid.UUID(lead["deal_id"]),
            )
            created.append({"type": "hot_lead", "action_id": str(a.id)})

    # Stalled deals → follow-up
    for deal in pipeline.get("stalled_deals", [])[:3]:
        a = await emit_action(
            db, org_id=org_id, action_type="follow_up_deal",
            title=f"Stalled: {deal['customer'][:40]} (${deal['value']:,.0f})",
            description=f"In '{deal['stage']}' for 14+ days. Follow up.",
            category="monetization", priority="medium",
            brand_id=brand_id, source_module="service_sales_engine",
        )
        created.append({"type": "stalled_deal", "action_id": str(a.id)})

    return created
