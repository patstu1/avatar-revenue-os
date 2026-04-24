"""Governance Bridge — makes governance real and memory persistent.

This service completes the operating system by:

1. Enforcing the permission matrix before critical actions
2. Creating structured audit trails with event integration
3. Connecting creative memory to the content generation loop
4. Surfacing governance state (gates, approvals, permissions) in the control layer
5. Building a continuity layer from memory entries

The existing governance infrastructure (workflow builder, permission matrix,
audit service, creative memory) handles the data. This bridge makes it
enforce, surface, and participate in the machine.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.audit_service import log_action
from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.core import Brand
from packages.db.models.creative_memory import CreativeMemoryAtom
from packages.db.models.gatekeeper import (
    GatekeeperAlert,
    GatekeeperContradictionReport,
)
from packages.db.models.learning import MemoryEntry
from packages.db.models.operator_permission_matrix import OperatorPermissionMatrix
from packages.db.models.quality import Approval
from packages.db.models.workflow_builder import WorkflowInstance

logger = structlog.get_logger()


# ── Permission Enforcement ──────────────────────────────────────────

async def check_permission(
    db: AsyncSession,
    org_id: uuid.UUID,
    action_class: str,
    user_role: str = "operator",
    *,
    actor_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
) -> dict:
    """Check the permission matrix before allowing an action.

    Returns {allowed, needs_approval, reason} and logs the check.
    This is the enforcement point — callers should respect the result.
    """
    from apps.api.services.operator_permission_service import check_action

    result = check_action.__wrapped__(db, org_id, action_class) if hasattr(check_action, '__wrapped__') else await check_action(db, org_id, action_class)

    # Log the permission check to audit trail
    await log_action(
        db, f"permission.checked.{action_class}",
        organization_id=org_id,
        user_id=uuid.UUID(actor_id) if actor_id else None,
        actor_type="human" if actor_id else "system",
        entity_type=entity_type,
        entity_id=entity_id,
        details={
            "action_class": action_class,
            "user_role": user_role,
            "allowed": result.get("allowed", True),
            "needs_approval": result.get("needs_approval", False),
        },
    )

    # If blocked, emit event + create operator action
    if result.get("needs_approval"):
        await emit_event(
            db, domain="governance", event_type="permission.approval_required",
            summary=f"Action '{action_class}' requires approval (role: {user_role})",
            org_id=org_id,
            entity_type=entity_type, entity_id=entity_id,
            severity="warning",
            details=result,
        )

    return result


# ── Structured Audit Trail ──────────────────────────────────────────

async def audit_state_transition(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    brand_id: Optional[uuid.UUID] = None,
    actor_id: Optional[str] = None,
    actor_type: str = "system",
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[dict] = None,
) -> dict:
    """Create a structured audit entry for a state transition.

    Combines audit logging + event emission in one call so that
    governance, control layer, and memory all see the transition.
    """
    # Audit log (immutable record)
    audit = await log_action(
        db, action,
        organization_id=org_id,
        brand_id=brand_id,
        user_id=uuid.UUID(actor_id) if actor_id else None,
        actor_type=actor_type,
        entity_type=entity_type,
        entity_id=entity_id,
        details={
            "previous_state": previous_state,
            "new_state": new_state,
            "reason": reason,
            **(details or {}),
        },
    )

    # System event (for control layer visibility)
    event = await emit_event(
        db, domain="governance", event_type=f"audit.{action}",
        summary=f"{entity_type} {action}: {previous_state or '?'} → {new_state or '?'}"
               + (f" ({reason})" if reason else ""),
        org_id=org_id, brand_id=brand_id,
        entity_type=entity_type, entity_id=entity_id,
        previous_state=previous_state,
        new_state=new_state,
        actor_type=actor_type,
        actor_id=actor_id,
        details={"audit_id": str(audit.id), "reason": reason, **(details or {})},
    )

    return {"audit_id": str(audit.id), "event_id": str(event.id)}


# ── Creative Memory Integration ──────────────────────────────────────

async def record_generation_outcome(
    db: AsyncSession,
    brand_id: uuid.UUID,
    content_item_id: uuid.UUID,
    *,
    generation_params: dict,
    quality_score: Optional[float] = None,
    approval_status: Optional[str] = None,
    performance_data: Optional[dict] = None,
) -> Optional[MemoryEntry]:
    """Record a content generation outcome for the memory layer.

    Captures what parameters were used, what quality was achieved,
    and whether the content was approved. This feeds the learning
    loop that improves future generations.
    """
    # Build memory summary
    model = generation_params.get("model", "unknown")
    platform = generation_params.get("platform", "unknown")

    summary_parts = [f"Generated via {model} for {platform}"]
    if quality_score is not None:
        summary_parts.append(f"QA score: {quality_score:.2f}")
    if approval_status:
        summary_parts.append(f"Status: {approval_status}")

    memory = MemoryEntry(
        brand_id=brand_id,
        memory_type="generation_outcome",
        key=f"content_{content_item_id}",
        value="; ".join(summary_parts),
        confidence=min(1.0, (quality_score or 0.5) * 1.2),
        source_type="content_lifecycle",
        source_content_id=content_item_id,
        structured_value={
            "generation_params": generation_params,
            "quality_score": quality_score,
            "approval_status": approval_status,
            "performance_data": performance_data,
        },
    )
    db.add(memory)
    await db.flush()

    logger.info(
        "governance_bridge.generation_outcome_recorded",
        brand_id=str(brand_id),
        content_id=str(content_item_id),
        quality_score=quality_score,
    )

    return memory


async def get_memory_context(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    memory_type: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Retrieve memory entries for decision context.

    Called before content generation, monetization decisions, or
    any action that benefits from historical context.
    """
    query = select(MemoryEntry).where(
        MemoryEntry.brand_id == brand_id,
    )
    if memory_type:
        query = query.where(MemoryEntry.memory_type == memory_type)

    query = query.order_by(MemoryEntry.confidence.desc(), MemoryEntry.created_at.desc()).limit(limit)
    results = (await db.execute(query)).scalars().all()

    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "key": m.key,
            "value": m.value,
            "confidence": m.confidence,
            "times_reinforced": m.times_reinforced,
            "times_contradicted": m.times_contradicted,
            "source_type": m.source_type,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in results
    ]


async def get_creative_atoms(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    atom_type: Optional[str] = None,
    min_confidence: float = 0.3,
    limit: int = 20,
) -> list[dict]:
    """Retrieve creative memory atoms for generation context.

    High-confidence atoms with low originality caution are good
    candidates for reuse. High-caution atoms should be avoided.
    """
    query = select(CreativeMemoryAtom).where(
        CreativeMemoryAtom.brand_id == brand_id,
        CreativeMemoryAtom.confidence_score >= min_confidence,
    )
    if atom_type:
        query = query.where(CreativeMemoryAtom.atom_type == atom_type)

    query = query.order_by(
        CreativeMemoryAtom.confidence_score.desc(),
    ).limit(limit)

    results = (await db.execute(query)).scalars().all()

    return [
        {
            "id": str(a.id),
            "atom_type": a.atom_type,
            "platform": a.platform,
            "niche": a.niche,
            "confidence_score": a.confidence_score,
            "originality_caution_score": a.originality_caution_score,
            "reuse_safe": (a.originality_caution_score or 0) < 0.7,
            "content_json": a.content_json,
            "reuse_recommendations": a.reuse_recommendations_json,
        }
        for a in results
    ]


# ── Governance Summary for Control Layer ──────────────────────────────

async def get_governance_summary(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> dict:
    """Aggregate governance state for the control layer.

    Shows approval pipeline, permission matrix state, gatekeeper
    status, and memory health — everything the operator needs
    to trust the system is operating safely.
    """
    brand_ids_q = select(Brand.id).where(Brand.organization_id == org_id)

    # Pending approvals
    pending_approvals = (await db.execute(
        select(func.count()).select_from(Approval).where(
            Approval.brand_id.in_(brand_ids_q),
            Approval.status == "pending",
        )
    )).scalar() or 0

    # Recent approvals/rejections (24h)
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    approved_24h = (await db.execute(
        select(func.count()).select_from(Approval).where(
            Approval.brand_id.in_(brand_ids_q),
            Approval.status == "approved",
            Approval.created_at >= day_ago,
        )
    )).scalar() or 0

    rejected_24h = (await db.execute(
        select(func.count()).select_from(Approval).where(
            Approval.brand_id.in_(brand_ids_q),
            Approval.status == "rejected",
            Approval.created_at >= day_ago,
        )
    )).scalar() or 0

    # Active workflows
    active_workflows = (await db.execute(
        select(func.count()).select_from(WorkflowInstance).where(
            WorkflowInstance.brand_id.in_(brand_ids_q),
            WorkflowInstance.status == "in_progress",
        )
    )).scalar() or 0

    # Permission matrix coverage
    permission_rules = (await db.execute(
        select(func.count()).select_from(OperatorPermissionMatrix).where(
            OperatorPermissionMatrix.organization_id == org_id,
            OperatorPermissionMatrix.is_active.is_(True),
        )
    )).scalar() or 0

    # Gatekeeper alerts
    gatekeeper_alerts = (await db.execute(
        select(func.count()).select_from(GatekeeperAlert).where(
            GatekeeperAlert.brand_id.in_(brand_ids_q),
            GatekeeperAlert.resolved.is_(False),
        )
    )).scalar() or 0

    # Memory entries
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

    # Contradictions (from gatekeeper)
    contradictions = (await db.execute(
        select(func.count()).select_from(GatekeeperContradictionReport).where(
            GatekeeperContradictionReport.brand_id.in_(brand_ids_q),
        )
    )).scalar() or 0

    return {
        "approvals": {
            "pending": pending_approvals,
            "approved_24h": approved_24h,
            "rejected_24h": rejected_24h,
        },
        "workflows": {
            "active": active_workflows,
        },
        "permissions": {
            "rules_defined": permission_rules,
        },
        "gatekeeper": {
            "open_alerts": gatekeeper_alerts,
            "contradictions": contradictions,
        },
        "memory": {
            "memory_entries": memory_entries,
            "creative_atoms": creative_atoms,
        },
    }


# ── Surface Governance Actions ──────────────────────────────────────

async def surface_governance_actions(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[dict]:
    """Scan governance state and create operator actions.

    Identifies pending approvals, unresolved gatekeeper alerts,
    and governance gaps that need operator attention.
    """
    actions_created = []
    brand_ids_q = select(Brand.id).where(Brand.organization_id == org_id)

    # 1. Stale pending approvals (> 24h old)
    stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
    stale_approvals = await db.execute(
        select(Approval).where(
            Approval.brand_id.in_(brand_ids_q),
            Approval.status == "pending",
            Approval.created_at < stale_threshold,
        ).limit(5)
    )
    for a in stale_approvals.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="review_stale_approval",
            title="Stale approval: content awaiting review > 24h",
            description="Content item has been waiting for approval for over 24 hours.",
            category="approval",
            priority="medium",
            brand_id=a.brand_id,
            entity_type="approval",
            entity_id=a.id,
            source_module="governance_bridge",
        )
        actions_created.append({"type": "stale_approval", "action_id": str(action.id)})

    # 2. Unresolved gatekeeper alerts
    alerts = await db.execute(
        select(GatekeeperAlert).where(
            GatekeeperAlert.brand_id.in_(brand_ids_q),
            GatekeeperAlert.resolved.is_(False),
            GatekeeperAlert.severity.in_(["critical", "high"]),
        ).limit(5)
    )
    for alert in alerts.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="resolve_gatekeeper_alert",
            title=f"Gatekeeper alert: {alert.alert_type if hasattr(alert, 'alert_type') else 'unknown'}",
            description=f"Severity: {alert.severity}. Requires resolution before proceeding.",
            category="governance",
            priority="critical" if alert.severity == "critical" else "high",
            brand_id=alert.brand_id,
            entity_type="gatekeeper_alert",
            entity_id=alert.id,
            source_module="gatekeeper",
        )
        actions_created.append({"type": "gatekeeper_alert", "action_id": str(action.id)})

    # 3. Permission matrix not seeded
    has_matrix = (await db.execute(
        select(func.count()).select_from(OperatorPermissionMatrix).where(
            OperatorPermissionMatrix.organization_id == org_id,
            OperatorPermissionMatrix.is_active.is_(True),
        )
    )).scalar() or 0

    if has_matrix == 0:
        action = await emit_action(
            db, org_id=org_id,
            action_type="seed_permission_matrix",
            title="Permission matrix not configured",
            description="No permission rules defined. Seed default policies to enable governance.",
            category="governance",
            priority="medium",
            source_module="governance_bridge",
        )
        actions_created.append({"type": "missing_matrix", "action_id": str(action.id)})

    # 4. Contradictions detected
    contradictions = await db.execute(
        select(GatekeeperContradictionReport).where(
            GatekeeperContradictionReport.brand_id.in_(brand_ids_q),
        ).order_by(GatekeeperContradictionReport.created_at.desc()).limit(3)
    )
    for c in contradictions.scalars().all():
        await emit_event(
            db, domain="governance", event_type="contradiction.detected",
            summary="Logic contradiction detected in brand operations",
            org_id=org_id, brand_id=c.brand_id,
            entity_type="contradiction_report", entity_id=c.id,
            severity="warning",
            requires_action=True,
        )

    await db.flush()
    return actions_created
