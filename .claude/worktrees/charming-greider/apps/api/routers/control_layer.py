"""Control Layer API — the operator's primary command surface.

This replaces fragmented dashboard endpoints with a unified operational API
that surfaces real system state, pending actions, and recent events.
"""
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.control_layer import (
    ActionCompleteRequest,
    ActionDismissRequest,
    ControlLayerDashboard,
    OperatorActionList,
    OperatorActionResponse,
    SystemEventList,
    SystemEventResponse,
    SystemHealthResponse,
)
from apps.api.services import control_layer_service as ctrl_svc
from apps.api.services.event_bus import complete_action, dismiss_action, emit_event
from packages.db.models.system_events import OperatorAction, SystemEvent

router = APIRouter()


@router.get("/control-layer/dashboard", response_model=ControlLayerDashboard)
async def get_control_layer(current_user: CurrentUser, db: DBSession):
    """The primary operator endpoint — complete system state in one call.

    Returns:
    - System health (entity counts, pipeline state, job state)
    - Pending operator actions (blockers, approvals, opportunities)
    - Recent system events (state changes, completions, failures)
    - Critical counts for badge indicators
    """
    org_id = current_user.organization_id
    data = await ctrl_svc.get_control_layer_dashboard(db, org_id)
    return ControlLayerDashboard(**data)


@router.get("/control-layer/health", response_model=SystemHealthResponse)
async def get_system_health(current_user: CurrentUser, db: DBSession):
    """Real-time system health snapshot."""
    org_id = current_user.organization_id
    data = await ctrl_svc.get_system_health(db, org_id)
    return SystemHealthResponse(**data)


@router.get("/control-layer/actions", response_model=OperatorActionList)
async def get_pending_actions(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=50, le=200),
    category: str = Query(default=None, description="Filter by category: blocker, approval, opportunity, failure, health, monetization"),
    priority: str = Query(default=None, description="Filter by priority: critical, high, medium, low"),
):
    """List pending operator actions — the things that need attention."""
    org_id = current_user.organization_id
    actions = await ctrl_svc.get_pending_actions(db, org_id, limit=limit)

    if category:
        actions = [a for a in actions if a["category"] == category]
    if priority:
        actions = [a for a in actions if a["priority"] == priority]

    pending_count = len(actions)
    critical_count = len([a for a in actions if a["priority"] == "critical"])

    return OperatorActionList(
        actions=[OperatorActionResponse(**a) for a in actions],
        total=pending_count,
        pending_count=pending_count,
        critical_count=critical_count,
    )


@router.post("/control-layer/actions/{action_id}/complete")
async def complete_operator_action(
    action_id: uuid.UUID,
    body: ActionCompleteRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Mark an operator action as completed."""
    org_id = current_user.organization_id
    action = (await db.execute(
        select(OperatorAction).where(
            and_(OperatorAction.id == action_id, OperatorAction.organization_id == org_id)
        )
    )).scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=400, detail=f"Action is already {action.status}")

    await complete_action(db, action, completed_by=str(current_user.id), result=body.result)
    await emit_event(
        db, domain="governance", event_type="action.completed",
        summary=f"Action completed: {action.title}",
        org_id=org_id, entity_type="operator_action", entity_id=action.id,
        actor_type="human", actor_id=str(current_user.id),
        details={"action_type": action.action_type, "result": body.result},
    )
    await db.commit()

    return {"status": "completed", "action_id": str(action_id)}


@router.post("/control-layer/actions/{action_id}/dismiss")
async def dismiss_operator_action(
    action_id: uuid.UUID,
    body: ActionDismissRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Dismiss an operator action."""
    org_id = current_user.organization_id
    action = (await db.execute(
        select(OperatorAction).where(
            and_(OperatorAction.id == action_id, OperatorAction.organization_id == org_id)
        )
    )).scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    await dismiss_action(db, action, dismissed_by=str(current_user.id))
    await db.commit()

    return {"status": "dismissed", "action_id": str(action_id)}


@router.get("/control-layer/events", response_model=SystemEventList)
async def get_system_events(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=50, le=200),
    domain: str = Query(default=None, description="Filter by domain: content, publishing, monetization, intelligence, orchestration, governance, recovery"),
    severity: str = Query(default=None, description="Filter by severity: info, warning, error, critical"),
):
    """List recent system events — the activity feed."""
    org_id = current_user.organization_id
    events = await ctrl_svc.get_recent_events(db, org_id, limit=limit)

    if domain:
        events = [e for e in events if e["event_domain"] == domain]
    if severity:
        events = [e for e in events if e["event_severity"] == severity]

    return SystemEventList(
        events=[SystemEventResponse(**e) for e in events],
        total=len(events),
    )
