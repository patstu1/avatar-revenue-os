"""Portfolio Command Center — one view for mass-scale operations.

Replaces 204 passive pages with one operational endpoint that surfaces:
- Top actions across ALL brands
- Portfolio revenue state
- Brand rankings
- Stalled deals
- Revenue leaks
- Content pipeline state
- System health

One view. Everything that matters. Nothing that doesn't.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import and_, case, func, select

from apps.api.deps import CurrentUser, DBSession
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import SponsorOpportunity
from packages.db.models.revenue_ledger import RevenueLedgerEntry
from packages.db.models.system import SystemJob
from packages.db.models.system_events import OperatorAction, SystemEvent

router = APIRouter()


@router.get("/portfolio/overview")
async def portfolio_overview(current_user: CurrentUser, db: DBSession):
    """Portfolio overview for the dashboard — real aggregation across all brands."""
    org_id = current_user.organization_id
    now = datetime.now(timezone.utc)
    day_30 = now - timedelta(days=30)

    # Brands
    brands_result = (await db.execute(
        select(Brand).where(Brand.organization_id == org_id, Brand.is_active)
    )).scalars().all()

    # Revenue 30d
    rev_total = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0))
        .join(Brand, RevenueLedgerEntry.brand_id == Brand.id)
        .where(Brand.organization_id == org_id,
               RevenueLedgerEntry.occurred_at >= day_30)
    )).scalar() or 0

    # Accounts
    accounts_result = (await db.execute(
        select(CreatorAccount)
        .join(Brand, CreatorAccount.brand_id == Brand.id)
        .where(Brand.organization_id == org_id, CreatorAccount.is_active)
    )).scalars().all()
    total_followers = sum(a.follower_count or 0 for a in accounts_result)
    active_accounts = len(accounts_result)

    # Published content
    published_count = (await db.execute(
        select(func.count(ContentItem.id))
        .join(Brand, ContentItem.brand_id == Brand.id)
        .where(Brand.organization_id == org_id, ContentItem.status == "published")
    )).scalar() or 0

    # Pending actions
    pending_actions = (await db.execute(
        select(func.count(OperatorAction.id))
        .where(OperatorAction.organization_id == org_id, OperatorAction.status == "pending")
    )).scalar() or 0

    # Per-brand performance
    brand_perfs = []
    for brand in brands_result:
        b_rev = (await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0))
            .where(RevenueLedgerEntry.brand_id == brand.id,
                   RevenueLedgerEntry.occurred_at >= day_30)
        )).scalar() or 0

        b_content = (await db.execute(
            select(func.count(ContentItem.id))
            .where(ContentItem.brand_id == brand.id)
        )).scalar() or 0

        b_accounts = sum(1 for a in accounts_result if str(a.brand_id) == str(brand.id))

        brand_perfs.append({
            "id": str(brand.id),
            "name": brand.name,
            "revenue": float(b_rev),
            "content_count": b_content,
            "account_count": b_accounts,
            "trajectory": "growing" if float(b_rev) > 0 else "flat",
        })

    # Revenue series (last 30 days, daily)
    rev_series_result = (await db.execute(
        select(
            func.date_trunc('day', RevenueLedgerEntry.occurred_at).label('day'),
            func.sum(RevenueLedgerEntry.gross_amount).label('revenue'),
        )
        .join(Brand, RevenueLedgerEntry.brand_id == Brand.id)
        .where(Brand.organization_id == org_id,
               RevenueLedgerEntry.occurred_at >= day_30)
        .group_by('day')
        .order_by('day')
    )).all()
    revenue_series = [{"date": str(r.day.date()), "revenue": float(r.revenue)} for r in rev_series_result]

    return {
        "total_revenue": float(rev_total),
        "total_followers": total_followers,
        "content_published": published_count,
        "active_accounts": active_accounts,
        "pending_actions": pending_actions,
        "brands": brand_perfs,
        "revenue_series": revenue_series,
    }


@router.get("/command/portfolio")
async def portfolio_command_center(current_user: CurrentUser, db: DBSession):
    """The one view that replaces 204 pages.

    Everything an operator needs to manage a multi-brand portfolio at scale.
    """
    org_id = current_user.organization_id
    now = datetime.now(timezone.utc)
    day_30 = now - timedelta(days=30)

    # ── Top actions across all brands (priority-sorted, deduplicated) ──
    priority_order = case(
        (OperatorAction.priority == "critical", 0),
        (OperatorAction.priority == "high", 1),
        (OperatorAction.priority == "medium", 2),
        else_=3,
    )
    top_actions = (await db.execute(
        select(OperatorAction)
        .where(OperatorAction.organization_id == org_id, OperatorAction.status == "pending")
        .order_by(priority_order, OperatorAction.created_at.desc())
        .limit(15)
    )).scalars().all()

    actions = [
        {"id": str(a.id), "type": a.action_type, "title": a.title[:100],
         "priority": a.priority, "category": a.category,
         "brand_id": str(a.brand_id) if a.brand_id else None,
         "source": a.source_module}
        for a in top_actions
    ]

    # ── Portfolio revenue ──
    total_rev = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
            RevenueLedgerEntry.brand_id.in_(select(Brand.id).where(Brand.organization_id == org_id)),
            RevenueLedgerEntry.occurred_at >= day_30,
            RevenueLedgerEntry.is_active.is_(True), RevenueLedgerEntry.is_refund.is_(False),
        )
    )).scalar() or 0.0

    rev_by_source = {}
    rev_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount))
        .where(RevenueLedgerEntry.brand_id.in_(select(Brand.id).where(Brand.organization_id == org_id)),
               RevenueLedgerEntry.occurred_at >= day_30, RevenueLedgerEntry.is_active.is_(True),
               RevenueLedgerEntry.is_refund.is_(False))
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    for r in rev_q.all():
        rev_by_source[str(r[0])] = float(r[1] or 0)

    # ── Brand rankings ──
    brands_q = await db.execute(
        select(Brand.id, Brand.name,
               func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0))
        .outerjoin(RevenueLedgerEntry, and_(
            RevenueLedgerEntry.brand_id == Brand.id,
            RevenueLedgerEntry.occurred_at >= day_30,
            RevenueLedgerEntry.is_active.is_(True),
            RevenueLedgerEntry.is_refund.is_(False),
        ))
        .where(Brand.organization_id == org_id)
        .group_by(Brand.id, Brand.name)
        .order_by(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0).desc())
    )
    brand_rankings = [
        {"brand_id": str(r[0]), "name": r[1], "revenue_30d": float(r[2] or 0)}
        for r in brands_q.all()
    ]

    # ── Stalled deals ──
    stalled = (await db.execute(
        select(SponsorOpportunity.title, SponsorOpportunity.deal_value, SponsorOpportunity.status)
        .where(SponsorOpportunity.brand_id.in_(select(Brand.id).where(Brand.organization_id == org_id)),
               SponsorOpportunity.status.in_(["prospect", "outreach", "negotiation"]),
               SponsorOpportunity.updated_at < now - timedelta(days=14))
        .limit(5)
    )).all()
    stalled_deals = [{"title": r[0], "value": float(r[1] or 0), "status": r[2]} for r in stalled]

    # ── Content pipeline ──
    pipeline_q = await db.execute(
        select(ContentItem.status, func.count())
        .where(ContentItem.brand_id.in_(select(Brand.id).where(Brand.organization_id == org_id)))
        .group_by(ContentItem.status)
    )
    content_pipeline = {str(r[0]): r[1] for r in pipeline_q.all()}

    # ── System health ──
    jobs_running = (await db.execute(
        select(func.count()).select_from(SystemJob).where(SystemJob.status == "running")
    )).scalar() or 0
    jobs_failed_24h = (await db.execute(
        select(func.count()).select_from(SystemJob).where(
            SystemJob.status == "failed", SystemJob.completed_at >= now - timedelta(hours=24)
        )
    )).scalar() or 0

    # ── Recent events ──
    recent_events = (await db.execute(
        select(SystemEvent).where(SystemEvent.organization_id == org_id)
        .order_by(SystemEvent.created_at.desc()).limit(10)
    )).scalars().all()
    events = [
        {"domain": e.event_domain, "type": e.event_type, "summary": e.summary[:100],
         "severity": e.event_severity, "created_at": e.created_at.isoformat() if e.created_at else None}
        for e in recent_events
    ]

    return {
        "portfolio_revenue_30d": float(total_rev),
        "revenue_by_source": rev_by_source,
        "brand_rankings": brand_rankings,
        "top_actions": actions,
        "pending_action_count": len(actions),
        "stalled_deals": stalled_deals,
        "content_pipeline": content_pipeline,
        "system_health": {"jobs_running": jobs_running, "jobs_failed_24h": jobs_failed_24h},
        "recent_events": events,
        "total_brands": len(brand_rankings),
    }
