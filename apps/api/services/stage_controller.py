"""Stage controller (Batch 4) — canonical stage rules + watchers.

Encodes the 11 stages of the revenue loop with:
  - entry condition (what row/event indicates entry)
  - success condition
  - timeout threshold (SLA)
  - allowed auto-actions
  - approval-required actions
  - escalation conditions

Provides:
  mark_stage(db, entity, stage, ...)         upsert StageState
  compute_sla_deadline(stage, entered_at)    per-stage SLA
  run_stuck_stage_watcher(db, org_id)        emits GMEscalation rows
                                              + escalation.stuck events
                                              for any entity past SLA
  request_approval(db, ...)                  idempotent GMApproval insert
  open_escalation(db, ...)                   idempotent GMEscalation insert
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.gm_control import (
    GMApproval,
    GMEscalation,
    StageState,
)

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
#  Stage catalogue
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StageSpec:
    stage: str
    entity_type: str
    timeout_minutes: int
    escalation_reason: str


# Narrow, from-the-spec subset. Every stage that materially gates
# revenue/fulfillment is represented. Extensible without schema change.
STAGE_CATALOGUE: dict[tuple[str, str], StageSpec] = {
    ("lead", "created"):                  StageSpec("created", "lead", 5, "lead_stuck_in_created"),
    ("lead", "routed"):                   StageSpec("routed", "lead", 10, "lead_not_routed"),
    ("lead", "outreach_active"):          StageSpec("outreach_active", "lead", 15, "outreach_not_sent"),
    ("email_reply_draft", "pending"):     StageSpec("pending", "email_reply_draft", 120, "draft_awaiting_approval"),
    ("email_reply_draft", "approved"):    StageSpec("approved", "email_reply_draft", 5, "approved_draft_not_sent"),
    ("proposal", "sent"):                 StageSpec("sent", "proposal", 60 * 24, "proposal_unpaid_24h"),
    ("payment", "pending"):               StageSpec("pending", "payment", 10, "payment_pending_too_long"),
    ("client", "active"):                 StageSpec("active", "client", 5, "client_active_no_intake"),
    ("intake_request", "sent"):           StageSpec("sent", "intake_request", 60 * 48, "intake_pending_48h"),
    ("production_job", "running"):        StageSpec("running", "production_job", 60 * 24, "production_idle_24h"),
    ("production_job", "qa_pending"):     StageSpec("qa_pending", "production_job", 30, "qa_idle_30m"),
    ("production_job", "qa_passed"):      StageSpec("qa_passed", "production_job", 15, "delivery_not_dispatched"),
}


def compute_sla_deadline(entity_type: str, stage: str, entered_at: datetime) -> datetime | None:
    spec = STAGE_CATALOGUE.get((entity_type, stage))
    if spec is None:
        return None
    return entered_at + timedelta(minutes=spec.timeout_minutes)


# ═══════════════════════════════════════════════════════════════════════════
#  Stage transitions
# ═══════════════════════════════════════════════════════════════════════════


async def mark_stage(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    stage: str,
    metadata: dict | None = None,
) -> StageState:
    """Upsert a StageState row, setting previous_stage + entered_at +
    SLA deadline. Resets ``is_stuck`` + ``stuck_reason`` on transition
    so a prior stuck label doesn't persist across stages."""
    existing = (
        await db.execute(
            select(StageState).where(
                StageState.entity_type == entity_type,
                StageState.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    deadline = compute_sla_deadline(entity_type, stage, now)

    if existing is None:
        state = StageState(
            org_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            stage=stage,
            previous_stage=None,
            entered_at=now,
            sla_deadline=deadline,
            metadata_json=metadata,
            is_stuck=False,
            stuck_reason=None,
        )
        db.add(state)
    else:
        if existing.stage != stage:
            existing.previous_stage = existing.stage
        existing.stage = stage
        existing.entered_at = now
        existing.sla_deadline = deadline
        existing.is_stuck = False
        existing.stuck_reason = None
        if metadata is not None:
            existing.metadata_json = metadata
        state = existing
    await db.flush()
    return state


# ═══════════════════════════════════════════════════════════════════════════
#  Approvals + escalations
# ═══════════════════════════════════════════════════════════════════════════


async def request_approval(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    action_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    title: str,
    description: str | None = None,
    reason: str | None = None,
    risk_level: str = "medium",
    proposed_payload: dict | None = None,
    confidence: float = 0.0,
    expires_in_hours: int | None = 72,
    source_module: str | None = None,
) -> tuple[GMApproval, bool]:
    """Idempotent GMApproval insert. Emits ``gm.approval.requested`` on
    first insert only. Returns (approval, is_new).
    """
    existing = (
        await db.execute(
            select(GMApproval).where(
                GMApproval.org_id == org_id,
                GMApproval.entity_type == entity_type,
                GMApproval.entity_id == entity_id,
                GMApproval.action_type == action_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return (existing, False)

    expires_at = None
    if expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

    approval = GMApproval(
        org_id=org_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title[:500],
        description=description,
        reason=reason,
        risk_level=risk_level,
        proposed_payload=proposed_payload,
        confidence=confidence,
        status="pending",
        expires_at=expires_at,
        source_module=source_module,
    )
    db.add(approval)
    await db.flush()

    await emit_event(
        db,
        domain="gm",
        event_type="gm.approval.requested",
        summary=f"Approval requested: {title[:80]}",
        org_id=org_id,
        entity_type="gm_approval",
        entity_id=approval.id,
        new_state="pending",
        actor_type="system",
        actor_id=source_module or "stage_controller",
        requires_action=True,
        details={
            "approval_id": str(approval.id),
            "action_type": action_type,
            "target_entity_type": entity_type,
            "target_entity_id": str(entity_id),
            "risk_level": risk_level,
            "confidence": confidence,
        },
    )
    logger.info(
        "gm.approval.requested",
        approval_id=str(approval.id),
        action_type=action_type,
        entity_type=entity_type,
    )
    return (approval, True)


async def resolve_approval(
    db: AsyncSession,
    *,
    approval: GMApproval,
    decision: str,  # approved | rejected
    decided_by: str,
    notes: str | None = None,
) -> GMApproval:
    if approval.status != "pending":
        raise ValueError(f"approval is {approval.status}, not pending")
    if decision not in ("approved", "rejected"):
        raise ValueError(f"invalid decision: {decision}")

    approval.status = decision
    approval.decided_at = datetime.now(timezone.utc)
    approval.decided_by = decided_by[:255]
    approval.decision_notes = notes
    await db.flush()

    await emit_event(
        db,
        domain="gm",
        event_type=f"gm.approval.{decision}",
        summary=f"Approval {decision}: {approval.title[:80]}",
        org_id=approval.org_id,
        entity_type="gm_approval",
        entity_id=approval.id,
        previous_state="pending",
        new_state=decision,
        actor_type="operator",
        actor_id=decided_by,
        details={
            "approval_id": str(approval.id),
            "action_type": approval.action_type,
            "decision_notes": notes,
        },
    )
    return approval


async def open_escalation(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    reason_code: str,
    title: str,
    description: str | None = None,
    severity: str = "warning",
    stage: str | None = None,
    details: dict | None = None,
    source_module: str | None = None,
) -> tuple[GMEscalation, bool]:
    """Idempotent GMEscalation insert. On duplicate, bumps
    occurrence_count + last_seen_at and emits a fresh escalation event.
    Returns (escalation, is_new).
    """
    existing = (
        await db.execute(
            select(GMEscalation).where(
                GMEscalation.org_id == org_id,
                GMEscalation.entity_type == entity_type,
                GMEscalation.entity_id == entity_id,
                GMEscalation.reason_code == reason_code,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.last_seen_at = now
        existing.occurrence_count = (existing.occurrence_count or 0) + 1
        if existing.status == "resolved":
            # Re-open if re-occurring
            existing.status = "open"
            existing.resolved_at = None
        await db.flush()
        return (existing, False)

    escalation = GMEscalation(
        org_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        reason_code=reason_code,
        stage=stage,
        title=title[:500],
        description=description,
        severity=severity,
        details_json=details,
        status="open",
        first_seen_at=now,
        last_seen_at=now,
        occurrence_count=1,
        source_module=source_module,
    )
    db.add(escalation)
    await db.flush()

    await emit_event(
        db,
        domain="gm",
        event_type="gm.escalation.opened",
        summary=f"Escalation opened: {title[:80]}",
        org_id=org_id,
        entity_type="gm_escalation",
        entity_id=escalation.id,
        new_state="open",
        actor_type="system",
        actor_id=source_module or "stage_controller",
        severity=severity,
        requires_action=True,
        details={
            "escalation_id": str(escalation.id),
            "reason_code": reason_code,
            "stage": stage,
            "target_entity_type": entity_type,
            "target_entity_id": str(entity_id),
            **(details or {}),
        },
    )
    logger.info(
        "gm.escalation.opened",
        escalation_id=str(escalation.id),
        reason_code=reason_code,
        entity_type=entity_type,
    )
    return (escalation, True)


async def resolve_escalation(
    db: AsyncSession,
    *,
    escalation: GMEscalation,
    resolved_by: str,
    notes: str | None = None,
) -> GMEscalation:
    if escalation.status == "resolved":
        return escalation
    now = datetime.now(timezone.utc)
    escalation.status = "resolved"
    escalation.resolved_at = now
    escalation.resolution_notes = notes
    escalation.acknowledged_at = escalation.acknowledged_at or now
    escalation.acknowledged_by = escalation.acknowledged_by or resolved_by
    await db.flush()

    await emit_event(
        db,
        domain="gm",
        event_type="gm.escalation.resolved",
        summary=f"Escalation resolved: {escalation.title[:80]}",
        org_id=escalation.org_id,
        entity_type="gm_escalation",
        entity_id=escalation.id,
        previous_state="open",
        new_state="resolved",
        actor_type="operator",
        actor_id=resolved_by,
        details={
            "escalation_id": str(escalation.id),
            "reason_code": escalation.reason_code,
            "resolution_notes": notes,
        },
    )
    return escalation


# ═══════════════════════════════════════════════════════════════════════════
#  Stuck-stage watcher
# ═══════════════════════════════════════════════════════════════════════════


async def run_stuck_stage_watcher(
    db: AsyncSession,
    *,
    org_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> dict:
    """Scan ``stage_states`` for entries past their SLA deadline and
    open an escalation for each. Optionally scoped to a single org.

    Returns ``{"checked": N, "stuck": M, "escalations_opened": K}``.
    """
    now = now or datetime.now(timezone.utc)

    q = select(StageState).where(
        StageState.is_active.is_(True),
        StageState.sla_deadline.is_not(None),
        StageState.sla_deadline < now,
    )
    if org_id is not None:
        q = q.where(StageState.org_id == org_id)

    rows = (await db.execute(q)).scalars().all()

    opened = 0
    stuck_count = 0
    for state in rows:
        spec = STAGE_CATALOGUE.get((state.entity_type, state.stage))
        if spec is None:
            continue

        if not state.is_stuck:
            state.is_stuck = True
            state.stuck_reason = spec.escalation_reason
            stuck_count += 1
        state.last_watcher_tick_at = now

        _, is_new = await open_escalation(
            db,
            org_id=state.org_id,
            entity_type=state.entity_type,
            entity_id=state.entity_id,
            reason_code=spec.escalation_reason,
            title=f"Stage stuck: {state.entity_type}/{state.stage} past SLA",
            description=(
                f"{state.entity_type} {state.entity_id} entered stage {state.stage} at "
                f"{(state.entered_at or now).isoformat()}, SLA was "
                f"{(state.sla_deadline or now).isoformat()} "
                f"(timeout {spec.timeout_minutes}m)"
            ),
            severity="warning",
            stage=state.stage,
            details={
                "entered_at": state.entered_at.isoformat() if state.entered_at else None,
                "sla_deadline": state.sla_deadline.isoformat() if state.sla_deadline else None,
                "timeout_minutes": spec.timeout_minutes,
            },
            source_module="stuck_stage_watcher",
        )
        if is_new:
            opened += 1

    await db.flush()
    return {
        "checked": len(rows),
        "stuck": stuck_count,
        "escalations_opened": opened,
    }
