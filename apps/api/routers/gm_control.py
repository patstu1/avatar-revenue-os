"""GM control-board router (Batch 4).

Endpoints:

  GET  /api/v1/gm/control-board
       single-fetch consolidated state: pending approvals, open
       escalations, stuck stages, counts of auto-handled actions +
       recent revenue events, in-flight stage entities.

  GET  /api/v1/gm/approvals
  POST /api/v1/gm/approvals/{id}/approve
  POST /api/v1/gm/approvals/{id}/reject

  GET  /api/v1/gm/escalations
  POST /api/v1/gm/escalations/{id}/acknowledge
  POST /api/v1/gm/escalations/{id}/resolve

  GET  /api/v1/gm/stage-states
  POST /api/v1/gm/watcher/run-now
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.stage_controller import (
    resolve_approval,
    resolve_escalation,
    run_stuck_stage_watcher,
)
from packages.db.models.gm_control import (
    GMApproval,
    GMEscalation,
    StageState,
)
from packages.db.models.system_events import OperatorAction, SystemEvent

logger = structlog.get_logger()

router = APIRouter(prefix="/gm", tags=["GM Control"])


# ── Control board (consolidated state) ──────────────────────────────────────


@router.get("/control-board")
async def control_board(
    current_user: OperatorUser,
    db: DBSession,
    lookback_hours: int = 24,
):
    """Single consolidated view. Returns the operator's queue state +
    summary counts for the last ``lookback_hours`` hours of activity.
    """
    org = current_user.organization_id
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, lookback_hours))

    pending_approvals = (
        await db.execute(
            select(GMApproval).where(
                GMApproval.org_id == org,
                GMApproval.status == "pending",
                GMApproval.is_active.is_(True),
            ).order_by(desc(GMApproval.created_at)).limit(50)
        )
    ).scalars().all()

    open_escalations = (
        await db.execute(
            select(GMEscalation).where(
                GMEscalation.org_id == org,
                GMEscalation.status.in_(("open", "acknowledged")),
                GMEscalation.is_active.is_(True),
            ).order_by(desc(GMEscalation.last_seen_at)).limit(50)
        )
    ).scalars().all()

    stuck_states = (
        await db.execute(
            select(StageState).where(
                StageState.org_id == org,
                StageState.is_stuck.is_(True),
                StageState.is_active.is_(True),
            ).order_by(StageState.sla_deadline.asc()).limit(50)
        )
    ).scalars().all()

    auto_handled_actions = (
        await db.execute(
            select(func.count()).select_from(OperatorAction).where(
                OperatorAction.organization_id == org,
                OperatorAction.status == "completed",
                OperatorAction.created_at >= since,
            )
        )
    ).scalar() or 0

    revenue_events_recent = (
        await db.execute(
            select(func.count()).select_from(SystemEvent).where(
                SystemEvent.organization_id == org,
                SystemEvent.event_domain.in_(("monetization", "fulfillment")),
                SystemEvent.created_at >= since,
            )
        )
    ).scalar() or 0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_hours": lookback_hours,
        "awaiting_approval": [_approval_summary(a) for a in pending_approvals],
        "escalated": [_escalation_summary(e) for e in open_escalations],
        "stuck_stages": [_stage_summary(s) for s in stuck_states],
        "auto_handled_count_recent": int(auto_handled_actions),
        "revenue_event_count_recent": int(revenue_events_recent),
    }


# ── Approvals ───────────────────────────────────────────────────────────────


@router.get("/approvals")
async def list_approvals(
    current_user: OperatorUser,
    db: DBSession,
    status: Optional[str] = None,
    limit: int = 50,
):
    q = select(GMApproval).where(
        GMApproval.org_id == current_user.organization_id,
        GMApproval.is_active.is_(True),
    )
    if status:
        q = q.where(GMApproval.status == status)
    q = q.order_by(desc(GMApproval.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_approval_summary(a) for a in rows]


class ApprovalDecisionBody(BaseModel):
    notes: Optional[str] = None


@router.post("/approvals/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    body: ApprovalDecisionBody,
    current_user: OperatorUser,
    db: DBSession,
):
    approval = await _require_owned(
        db, GMApproval, approval_id, current_user.organization_id, "Approval"
    )
    try:
        approval = await resolve_approval(
            db, approval=approval, decision="approved",
            decided_by=current_user.email, notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await db.commit()
    return _approval_summary(approval)


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    body: ApprovalDecisionBody,
    current_user: OperatorUser,
    db: DBSession,
):
    approval = await _require_owned(
        db, GMApproval, approval_id, current_user.organization_id, "Approval"
    )
    try:
        approval = await resolve_approval(
            db, approval=approval, decision="rejected",
            decided_by=current_user.email, notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await db.commit()
    return _approval_summary(approval)


# ── Escalations ─────────────────────────────────────────────────────────────


@router.get("/escalations")
async def list_escalations(
    current_user: OperatorUser,
    db: DBSession,
    status: Optional[str] = None,
    limit: int = 50,
):
    q = select(GMEscalation).where(
        GMEscalation.org_id == current_user.organization_id,
        GMEscalation.is_active.is_(True),
    )
    if status:
        q = q.where(GMEscalation.status == status)
    q = q.order_by(desc(GMEscalation.last_seen_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_escalation_summary(e) for e in rows]


class EscalationDecisionBody(BaseModel):
    notes: Optional[str] = None


@router.post("/escalations/{escalation_id}/acknowledge")
async def acknowledge_escalation(
    escalation_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    escalation = await _require_owned(
        db, GMEscalation, escalation_id, current_user.organization_id, "Escalation"
    )
    if escalation.status == "open":
        escalation.status = "acknowledged"
        escalation.acknowledged_at = datetime.now(timezone.utc)
        escalation.acknowledged_by = current_user.email
        await db.commit()
    return _escalation_summary(escalation)


@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation_route(
    escalation_id: str,
    body: EscalationDecisionBody,
    current_user: OperatorUser,
    db: DBSession,
):
    escalation = await _require_owned(
        db, GMEscalation, escalation_id, current_user.organization_id, "Escalation"
    )
    escalation = await resolve_escalation(
        db, escalation=escalation, resolved_by=current_user.email, notes=body.notes,
    )
    await db.commit()
    return _escalation_summary(escalation)


# ── Stage states ────────────────────────────────────────────────────────────


@router.get("/stage-states")
async def list_stage_states(
    current_user: OperatorUser,
    db: DBSession,
    entity_type: Optional[str] = None,
    stuck_only: bool = False,
    limit: int = 50,
):
    q = select(StageState).where(
        StageState.org_id == current_user.organization_id,
        StageState.is_active.is_(True),
    )
    if entity_type:
        q = q.where(StageState.entity_type == entity_type)
    if stuck_only:
        q = q.where(StageState.is_stuck.is_(True))
    q = q.order_by(desc(StageState.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_stage_summary(s) for s in rows]


@router.post("/watcher/run-now")
async def run_watcher_now(
    current_user: OperatorUser,
    db: DBSession,
):
    """Manually trigger the stuck-stage watcher for this operator's org."""
    result = await run_stuck_stage_watcher(db, org_id=current_user.organization_id)
    await db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _approval_summary(a: GMApproval) -> dict:
    return {
        "id": str(a.id),
        "action_type": a.action_type,
        "entity_type": a.entity_type,
        "entity_id": str(a.entity_id),
        "title": a.title,
        "reason": a.reason,
        "risk_level": a.risk_level,
        "confidence": a.confidence,
        "status": a.status,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "decided_by": a.decided_by,
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "created_at": a.created_at.isoformat(),
    }


def _escalation_summary(e: GMEscalation) -> dict:
    return {
        "id": str(e.id),
        "entity_type": e.entity_type,
        "entity_id": str(e.entity_id),
        "reason_code": e.reason_code,
        "stage": e.stage,
        "title": e.title,
        "severity": e.severity,
        "status": e.status,
        "occurrence_count": e.occurrence_count,
        "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
        "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "resolved_by": e.acknowledged_by,
        "created_at": e.created_at.isoformat(),
    }


def _stage_summary(s: StageState) -> dict:
    return {
        "id": str(s.id),
        "entity_type": s.entity_type,
        "entity_id": str(s.entity_id),
        "stage": s.stage,
        "previous_stage": s.previous_stage,
        "entered_at": s.entered_at.isoformat() if s.entered_at else None,
        "sla_deadline": s.sla_deadline.isoformat() if s.sla_deadline else None,
        "is_stuck": s.is_stuck,
        "stuck_reason": s.stuck_reason,
    }


async def _require_owned(db, model, row_id: str, org_id: uuid.UUID, label: str):
    try:
        rid = uuid.UUID(row_id)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Invalid {label} id")
    row = (
        await db.execute(select(model).where(model.id == rid))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"{label} not found")
    if row.org_id != org_id:
        raise HTTPException(403, f"{label} belongs to another organization")
    return row
