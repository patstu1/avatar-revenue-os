"""Governance Hub API — unified governance + memory surface for the operator.

Makes governance observable and memory accessible: approval state,
permission enforcement, audit trail, gatekeeper health, creative memory,
and learning context — all in one operational API.
"""

import uuid

from fastapi import APIRouter, Query

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import governance_bridge as gov

router = APIRouter()


@router.get("/governance/summary")
async def get_governance_summary(
    current_user: CurrentUser,
    db: DBSession,
):
    """Governance state: approvals, workflows, permissions, gatekeeper, memory."""
    return await gov.get_governance_summary(db, current_user.organization_id)


@router.get("/governance/memory")
async def get_memory_context(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    memory_type: str = Query(None),
    limit: int = Query(20, le=100),
):
    """Learning memory entries for decision context."""
    return await gov.get_memory_context(db, brand_id, memory_type=memory_type, limit=limit)


@router.get("/governance/creative-atoms")
async def get_creative_atoms(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    atom_type: str = Query(None),
    min_confidence: float = Query(0.3),
    limit: int = Query(20, le=100),
):
    """Creative memory atoms: reusable content patterns with confidence scores."""
    return await gov.get_creative_atoms(
        db,
        brand_id,
        atom_type=atom_type,
        min_confidence=min_confidence,
        limit=limit,
    )


@router.post("/governance/check-permission")
async def check_permission(
    current_user: OperatorUser,
    db: DBSession,
    action_class: str = Query(...),
):
    """Check if an action is permitted by the governance matrix."""
    result = await gov.check_permission(
        db,
        current_user.organization_id,
        action_class,
        user_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        actor_id=str(current_user.id),
    )
    await db.commit()
    return result


@router.post("/governance/record-outcome")
async def record_generation_outcome(
    current_user: OperatorUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    content_item_id: uuid.UUID = Query(...),
    quality_score: float = Query(None),
    approval_status: str = Query(None),
):
    """Record a content generation outcome for the memory layer."""
    entry = await gov.record_generation_outcome(
        db,
        brand_id,
        content_item_id,
        generation_params={"recorded_by": str(current_user.id)},
        quality_score=quality_score,
        approval_status=approval_status,
    )
    await db.commit()
    return {"status": "recorded", "memory_id": str(entry.id) if entry else None}


@router.post("/governance/surface-actions")
async def surface_governance_actions(
    current_user: OperatorUser,
    db: DBSession,
):
    """Scan for stale approvals, gatekeeper alerts, and governance gaps."""
    actions = await gov.surface_governance_actions(db, current_user.organization_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}
