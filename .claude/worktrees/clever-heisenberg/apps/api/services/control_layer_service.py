"""Control Layer Service — aggregates real system state for the operator.

This is the brain of the control layer. It queries across multiple tables
to build a real-time picture of system health, pending actions, and recent
events. Unlike the old dashboard that showed static counts, this surfaces
operational state that drives action.
"""
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import JobStatus
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem, MediaJob
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.publishing import PublishJob
from packages.db.models.system import ProviderUsageCost, SystemJob
from packages.db.models.system_events import OperatorAction, SystemEvent, SystemHealthSnapshot

logger = structlog.get_logger()


async def get_system_health(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Build a real-time health snapshot by querying actual system state.

    This replaces the old static-count dashboard with operational intelligence.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    month_ago = now - timedelta(days=30)

    brand_ids_q = select(Brand.id).where(Brand.organization_id == org_id)

    # --- Entity counts ---
    brands_count = (await db.execute(
        select(func.count()).select_from(Brand).where(Brand.organization_id == org_id)
    )).scalar() or 0

    accounts_count = (await db.execute(
        select(func.count()).select_from(CreatorAccount).where(
            CreatorAccount.brand_id.in_(brand_ids_q)
        )
    )).scalar() or 0

    offers_count = (await db.execute(
        select(func.count()).select_from(Offer).where(Offer.brand_id.in_(brand_ids_q))
    )).scalar() or 0

    content_total = (await db.execute(
        select(func.count()).select_from(ContentItem).where(
            ContentItem.brand_id.in_(brand_ids_q)
        )
    )).scalar() or 0

    # --- Content pipeline state (real status distribution) ---
    content_status_q = await db.execute(
        select(ContentItem.status, func.count())
        .where(ContentItem.brand_id.in_(brand_ids_q))
        .group_by(ContentItem.status)
    )
    content_by_status = {str(row[0]): row[1] for row in content_status_q.all()}

    # --- Job state ---
    job_status_q = await db.execute(
        select(SystemJob.status, func.count())
        .group_by(SystemJob.status)
    )
    jobs_by_status = {}
    for row in job_status_q.all():
        key = row[0].value if hasattr(row[0], 'value') else str(row[0])
        jobs_by_status[key] = row[1]

    jobs_completed_24h = (await db.execute(
        select(func.count()).select_from(SystemJob).where(
            and_(SystemJob.status == JobStatus.COMPLETED, SystemJob.completed_at >= day_ago)
        )
    )).scalar() or 0

    jobs_failed_24h = (await db.execute(
        select(func.count()).select_from(SystemJob).where(
            and_(SystemJob.status == JobStatus.FAILED, SystemJob.completed_at >= day_ago)
        )
    )).scalar() or 0

    # --- Operator actions ---
    actions_pending = (await db.execute(
        select(func.count()).select_from(OperatorAction).where(
            and_(OperatorAction.organization_id == org_id, OperatorAction.status == "pending")
        )
    )).scalar() or 0

    actions_critical = (await db.execute(
        select(func.count()).select_from(OperatorAction).where(
            and_(
                OperatorAction.organization_id == org_id,
                OperatorAction.status == "pending",
                OperatorAction.priority == "critical",
            )
        )
    )).scalar() or 0

    actions_completed_24h = (await db.execute(
        select(func.count()).select_from(OperatorAction).where(
            and_(
                OperatorAction.organization_id == org_id,
                OperatorAction.status == "completed",
                OperatorAction.completed_at >= day_ago,
            )
        )
    )).scalar() or 0

    # --- Provider cost ---
    total_cost = (await db.execute(
        select(func.coalesce(func.sum(ProviderUsageCost.cost), 0.0)).where(
            and_(
                ProviderUsageCost.brand_id.in_(brand_ids_q),
                ProviderUsageCost.created_at >= month_ago,
            )
        )
    )).scalar() or 0.0

    return {
        "total_brands": brands_count,
        "total_accounts": accounts_count,
        "total_offers": offers_count,
        "total_content_items": content_total,
        "content_draft": content_by_status.get("draft", 0),
        "content_generating": content_by_status.get("generating", 0),
        "content_review": content_by_status.get("qa_review", 0) + content_by_status.get("review", 0),
        "content_approved": content_by_status.get("approved", 0),
        "content_publishing": content_by_status.get("publishing", 0),
        "content_published": content_by_status.get("published", 0),
        "content_failed": content_by_status.get("failed", 0),
        "jobs_pending": jobs_by_status.get("pending", 0) + jobs_by_status.get("queued", 0),
        "jobs_running": jobs_by_status.get("running", 0),
        "jobs_completed_24h": jobs_completed_24h,
        "jobs_failed_24h": jobs_failed_24h,
        "jobs_retrying": jobs_by_status.get("retrying", 0),
        "actions_pending": actions_pending,
        "actions_critical": actions_critical,
        "actions_completed_24h": actions_completed_24h,
        "active_blockers": 0,  # Will be wired to gatekeeper in Phase 2
        "active_alerts": 0,  # Will be wired to scale_alerts in Phase 2
        "total_revenue_30d": await _get_total_revenue_30d(db, brand_ids_q, month_ago),
        "total_cost_30d": float(total_cost),
        "providers_healthy": await _get_provider_counts(db, "healthy"),
        "providers_degraded": await _get_provider_counts(db, "degraded"),
        "providers_down": await _get_provider_counts(db, "blocked"),
        "snapshot_at": now.isoformat(),
    }


async def _get_provider_counts(db: AsyncSession, status_type: str) -> int:
    """Count providers by health status from the canonical IntegrationProvider table.

    Health states set by health_monitor_worker: healthy, configured, unconfigured,
    auth_failed, unreachable.
    """
    from packages.db.models.integration_registry import IntegrationProvider

    if status_type == "healthy":
        return (await db.execute(
            select(func.count()).select_from(IntegrationProvider).where(
                IntegrationProvider.is_enabled.is_(True),
                IntegrationProvider.health_status.in_(["healthy", "configured"]),
            )
        )).scalar() or 0

    if status_type == "degraded":
        return (await db.execute(
            select(func.count()).select_from(IntegrationProvider).where(
                IntegrationProvider.is_enabled.is_(True),
                IntegrationProvider.health_status.in_(["auth_failed", "unconfigured"]),
            )
        )).scalar() or 0

    if status_type == "blocked":
        return (await db.execute(
            select(func.count()).select_from(IntegrationProvider).where(
                IntegrationProvider.is_enabled.is_(True),
                IntegrationProvider.health_status == "unreachable",
            )
        )).scalar() or 0

    return 0


async def _get_total_revenue_30d(db: AsyncSession, brand_ids_q, month_ago) -> float:
    """Aggregate revenue from the canonical ledger (primary) with legacy fallback."""
    from packages.db.models.revenue_ledger import RevenueLedgerEntry

    # Primary: canonical revenue ledger
    ledger = (await db.execute(
        select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
            RevenueLedgerEntry.brand_id.in_(brand_ids_q),
            RevenueLedgerEntry.occurred_at >= month_ago,
            RevenueLedgerEntry.is_active.is_(True),
        )
    )).scalar() or 0.0

    if float(ledger) > 0:
        return float(ledger)

    # Fallback: legacy sources if ledger is empty
    from packages.db.models.creator_revenue import CreatorRevenueEvent
    from packages.db.models.publishing import PerformanceMetric

    perf = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
            PerformanceMetric.brand_id.in_(brand_ids_q),
            PerformanceMetric.created_at >= month_ago,
        )
    )).scalar() or 0.0

    creator = (await db.execute(
        select(func.coalesce(func.sum(CreatorRevenueEvent.revenue), 0.0)).where(
            CreatorRevenueEvent.brand_id.in_(brand_ids_q),
            CreatorRevenueEvent.created_at >= month_ago,
        )
    )).scalar() or 0.0

    return float(perf) + float(creator)


async def get_pending_actions(
    db: AsyncSession, org_id: uuid.UUID, limit: int = 20
) -> list[dict]:
    """Get pending operator actions, ordered by priority and recency."""
    priority_order = case(
        (OperatorAction.priority == "critical", 0),
        (OperatorAction.priority == "high", 1),
        (OperatorAction.priority == "medium", 2),
        (OperatorAction.priority == "low", 3),
        else_=4,
    )

    q = await db.execute(
        select(OperatorAction)
        .where(
            and_(
                OperatorAction.organization_id == org_id,
                OperatorAction.status == "pending",
            )
        )
        .order_by(priority_order, OperatorAction.created_at.desc())
        .limit(limit)
    )
    actions = q.scalars().all()
    return [
        {
            "id": str(a.id),
            "action_type": a.action_type,
            "title": a.title,
            "description": a.description,
            "priority": a.priority,
            "category": a.category,
            "entity_type": a.entity_type,
            "entity_id": str(a.entity_id) if a.entity_id else None,
            "brand_id": str(a.brand_id) if a.brand_id else None,
            "source_module": a.source_module,
            "status": a.status,
            "action_payload": a.action_payload or {},
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        }
        for a in actions
    ]


async def get_recent_events(
    db: AsyncSession, org_id: uuid.UUID, limit: int = 30
) -> list[dict]:
    """Get recent system events for the activity feed."""
    q = await db.execute(
        select(SystemEvent)
        .where(SystemEvent.organization_id == org_id)
        .order_by(SystemEvent.created_at.desc())
        .limit(limit)
    )
    events = q.scalars().all()
    return [
        {
            "id": str(e.id),
            "event_domain": e.event_domain,
            "event_type": e.event_type,
            "event_severity": e.event_severity,
            "entity_type": e.entity_type,
            "entity_id": str(e.entity_id) if e.entity_id else None,
            "previous_state": e.previous_state,
            "new_state": e.new_state,
            "actor_type": e.actor_type,
            "summary": e.summary,
            "details": e.details or {},
            "requires_action": e.requires_action,
            "action_taken": e.action_taken,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


async def get_control_layer_dashboard(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Build the complete control layer dashboard.

    This is the primary operator endpoint — everything needed to understand
    system state and take action, in one call. Now includes intelligence counts.
    """
    health = await get_system_health(db, org_id)
    actions = await get_pending_actions(db, org_id)
    events = await get_recent_events(db, org_id)

    # Intelligence counts (lightweight — just counts, not full summary)
    intel_counts = await _get_intelligence_counts(db, org_id)

    # Governance summary
    governance = await _get_governance_counts(db, org_id)

    return {
        "health": health,
        "pending_actions": actions,
        "recent_events": events,
        "critical_count": health["actions_critical"],
        "pending_action_count": health["actions_pending"],
        "failed_jobs_24h": health["jobs_failed_24h"],
        "intelligence": intel_counts,
        "governance": governance,
    }


async def _get_governance_counts(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Lightweight governance counts for the control layer."""
    from packages.db.models.creative_memory import CreativeMemoryAtom
    from packages.db.models.gatekeeper import GatekeeperAlert
    from packages.db.models.learning import MemoryEntry
    from packages.db.models.quality import Approval

    brand_ids_q = select(Brand.id).where(Brand.organization_id == org_id)

    pending_approvals = (await db.execute(
        select(func.count()).select_from(Approval).where(
            Approval.brand_id.in_(brand_ids_q),
            Approval.status == "pending",
        )
    )).scalar() or 0

    open_alerts = (await db.execute(
        select(func.count()).select_from(GatekeeperAlert).where(
            GatekeeperAlert.brand_id.in_(brand_ids_q),
            GatekeeperAlert.resolved.is_(False),
        )
    )).scalar() or 0

    memory_entries = (await db.execute(
        select(func.count()).select_from(MemoryEntry).where(
            MemoryEntry.brand_id.in_(brand_ids_q),
        )
    )).scalar() or 0

    creative_atoms = (await db.execute(
        select(func.count()).select_from(CreativeMemoryAtom).where(
            CreativeMemoryAtom.brand_id.in_(brand_ids_q),
        )
    )).scalar() or 0

    return {
        "pending_approvals": pending_approvals,
        "open_alerts": open_alerts,
        "memory_entries": memory_entries,
        "creative_atoms": creative_atoms,
    }


async def _get_intelligence_counts(db: AsyncSession, org_id: uuid.UUID) -> dict:
    """Lightweight intelligence counts for the control layer header."""
    from packages.db.models.brain_phase_b import BrainDecision
    from packages.db.models.failure_family import SuppressionRule
    from packages.db.models.pattern_memory import WinningPatternMemory
    from packages.db.models.promote_winner import ActiveExperiment

    brand_ids_q = select(Brand.id).where(Brand.organization_id == org_id)

    winning = (await db.execute(
        select(func.count()).select_from(WinningPatternMemory).where(
            WinningPatternMemory.brand_id.in_(brand_ids_q),
            WinningPatternMemory.is_active.is_(True),
        )
    )).scalar() or 0

    decisions = (await db.execute(
        select(func.count()).select_from(BrainDecision).where(
            BrainDecision.brand_id.in_(brand_ids_q),
            BrainDecision.is_active.is_(True),
        )
    )).scalar() or 0

    experiments = (await db.execute(
        select(func.count()).select_from(ActiveExperiment).where(
            ActiveExperiment.brand_id.in_(brand_ids_q),
            ActiveExperiment.status == "active",
        )
    )).scalar() or 0

    suppressions = (await db.execute(
        select(func.count()).select_from(SuppressionRule).where(
            SuppressionRule.brand_id.in_(brand_ids_q),
            SuppressionRule.is_active.is_(True),
        )
    )).scalar() or 0

    return {
        "winning_patterns": winning,
        "active_decisions": decisions,
        "active_experiments": experiments,
        "active_suppressions": suppressions,
    }
