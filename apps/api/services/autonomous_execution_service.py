"""Autonomous execution control plane — policies, runs, blocker escalations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.autonomous_execution import (
    AutomationExecutionPolicy,
    AutomationExecutionRun,
    ExecutionBlockerEscalation,
)
from packages.db.models.core import Brand
from packages.db.models.scale_alerts import NotificationDelivery
from packages.scoring.autonomous_execution_engine import (
    AUTONOMOUS_LOOP_STEPS,
    evaluate_execution_gate,
)

VALID_MODES = frozenset({"fully_autonomous", "guarded_autonomous", "escalation_only"})


def _policy_snapshot(p: AutomationExecutionPolicy) -> dict[str, Any]:
    return {
        "operating_mode": p.operating_mode,
        "min_confidence_auto_execute": p.min_confidence_auto_execute,
        "min_confidence_publish": p.min_confidence_publish,
        "kill_switch_engaged": p.kill_switch_engaged,
        "max_auto_cost_usd_per_action": p.max_auto_cost_usd_per_action,
        "require_approval_above_cost_usd": p.require_approval_above_cost_usd,
        "approval_gates_json": p.approval_gates_json or {},
    }


def _policy_out(p: AutomationExecutionPolicy) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "brand_id": str(p.brand_id),
        "organization_id": str(p.organization_id) if p.organization_id else None,
        "operating_mode": p.operating_mode,
        "min_confidence_auto_execute": p.min_confidence_auto_execute,
        "min_confidence_publish": p.min_confidence_publish,
        "kill_switch_engaged": p.kill_switch_engaged,
        "max_auto_cost_usd_per_action": p.max_auto_cost_usd_per_action,
        "require_approval_above_cost_usd": p.require_approval_above_cost_usd,
        "approval_gates_json": p.approval_gates_json,
        "extra_policy_json": p.extra_policy_json,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _run_out(r: AutomationExecutionRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "loop_step": r.loop_step,
        "status": r.status,
        "confidence_score": r.confidence_score,
        "policy_snapshot_json": r.policy_snapshot_json,
        "input_payload_json": r.input_payload_json,
        "output_payload_json": r.output_payload_json,
        "blocked_reason": r.blocked_reason,
        "error_message": r.error_message,
        "approval_status": r.approval_status,
        "parent_run_id": str(r.parent_run_id) if r.parent_run_id else None,
        "rollback_of_run_id": str(r.rollback_of_run_id) if r.rollback_of_run_id else None,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _steps_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "steps" in raw and isinstance(raw["steps"], list):
        return raw["steps"]
    return []


def _blocker_out(b: ExecutionBlockerEscalation) -> dict[str, Any]:
    steps = _steps_list(b.exact_operator_steps_json)
    return {
        "id": str(b.id),
        "brand_id": str(b.brand_id),
        "blocker_category": b.blocker_category,
        "severity": b.severity,
        "title": b.title,
        "summary": b.summary,
        "exact_operator_steps_json": steps,
        "linked_run_id": str(b.linked_run_id) if b.linked_run_id else None,
        "risk_flags_json": b.risk_flags_json,
        "cost_exposure_json": b.cost_exposure_json,
        "resolution_status": b.resolution_status,
        "resolved_at": b.resolved_at,
        "resolved_by_user_id": str(b.resolved_by_user_id) if b.resolved_by_user_id else None,
        "resolution_notes": b.resolution_notes,
        "notification_enqueued_at": b.notification_enqueued_at,
        "is_active": b.is_active,
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


async def ensure_default_policy(db: AsyncSession, brand_id: uuid.UUID) -> AutomationExecutionPolicy:
    row = (
        await db.execute(
            select(AutomationExecutionPolicy).where(
                AutomationExecutionPolicy.brand_id == brand_id,
                AutomationExecutionPolicy.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row:
        return row
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")
    p = AutomationExecutionPolicy(
        brand_id=brand_id,
        organization_id=brand.organization_id,
        operating_mode="guarded_autonomous",
        min_confidence_auto_execute=0.72,
        min_confidence_publish=0.78,
        kill_switch_engaged=False,
        max_auto_cost_usd_per_action=250.0,
        require_approval_above_cost_usd=75.0,
        approval_gates_json={"publish_queue": "approval_required_by_default"},
        extra_policy_json={"loop_steps_registered": list(AUTONOMOUS_LOOP_STEPS)},
    )
    db.add(p)
    await db.flush()
    return p


async def get_policy(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    p = await ensure_default_policy(db, brand_id)
    return _policy_out(p)


async def update_policy(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    operating_mode: str | None = None,
    min_confidence_auto_execute: float | None = None,
    min_confidence_publish: float | None = None,
    kill_switch_engaged: bool | None = None,
    max_auto_cost_usd_per_action: float | None = None,
    require_approval_above_cost_usd: float | None = None,
    approval_gates_json: dict | None = None,
    extra_policy_json: dict | None = None,
) -> dict[str, Any]:
    p = await ensure_default_policy(db, brand_id)
    if operating_mode is not None:
        if operating_mode not in VALID_MODES:
            raise ValueError(f"Invalid operating_mode: {operating_mode}")
        p.operating_mode = operating_mode
    if min_confidence_auto_execute is not None:
        p.min_confidence_auto_execute = float(min_confidence_auto_execute)
    if min_confidence_publish is not None:
        p.min_confidence_publish = float(min_confidence_publish)
    if kill_switch_engaged is not None:
        p.kill_switch_engaged = bool(kill_switch_engaged)
    if max_auto_cost_usd_per_action is not None:
        p.max_auto_cost_usd_per_action = float(max_auto_cost_usd_per_action)
    if require_approval_above_cost_usd is not None:
        p.require_approval_above_cost_usd = float(require_approval_above_cost_usd)
    if approval_gates_json is not None:
        p.approval_gates_json = approval_gates_json
    if extra_policy_json is not None:
        p.extra_policy_json = extra_policy_json
    await db.flush()
    return _policy_out(p)


async def preview_gate(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    loop_step: str,
    confidence: float,
    estimated_cost_usd: float | None,
) -> dict[str, Any]:
    if loop_step not in AUTONOMOUS_LOOP_STEPS:
        raise ValueError(f"Unknown loop_step: {loop_step}")
    p = await ensure_default_policy(db, brand_id)
    return evaluate_execution_gate(
        operating_mode=p.operating_mode,
        kill_switch_engaged=p.kill_switch_engaged,
        loop_step=loop_step,
        confidence=confidence,
        estimated_cost_usd=estimated_cost_usd,
        min_confidence_auto_execute=p.min_confidence_auto_execute,
        min_confidence_publish=p.min_confidence_publish,
        max_auto_cost_usd_per_action=p.max_auto_cost_usd_per_action,
        require_approval_above_cost_usd=p.require_approval_above_cost_usd,
    )


async def create_execution_run(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    loop_step: str,
    status: str,
    confidence_score: float,
    input_payload_json: dict | None,
) -> dict[str, Any]:
    if loop_step not in AUTONOMOUS_LOOP_STEPS:
        raise ValueError(f"Unknown loop_step: {loop_step}")
    p = await ensure_default_policy(db, brand_id)
    run = AutomationExecutionRun(
        brand_id=brand_id,
        loop_step=loop_step,
        status=status,
        confidence_score=float(confidence_score),
        policy_snapshot_json=_policy_snapshot(p),
        input_payload_json=input_payload_json or {},
    )
    db.add(run)
    await db.flush()
    return _run_out(run)


async def update_run_status(
    db: AsyncSession,
    brand_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    status: str | None = None,
    output_payload_json: dict | None = None,
    blocked_reason: str | None = None,
    error_message: str | None = None,
    approval_status: str | None = None,
) -> dict[str, Any]:
    run = (
        await db.execute(
            select(AutomationExecutionRun).where(
                AutomationExecutionRun.id == run_id,
                AutomationExecutionRun.brand_id == brand_id,
            )
        )
    ).scalar_one_or_none()
    if not run:
        raise ValueError("Run not found")
    if status is not None:
        run.status = status
    if output_payload_json is not None:
        run.output_payload_json = output_payload_json
    if blocked_reason is not None:
        run.blocked_reason = blocked_reason
    if error_message is not None:
        run.error_message = error_message
    if approval_status is not None:
        run.approval_status = approval_status
    await db.flush()
    return _run_out(run)


async def mark_run_rollback(
    db: AsyncSession, brand_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    run = (
        await db.execute(
            select(AutomationExecutionRun).where(
                AutomationExecutionRun.id == run_id,
                AutomationExecutionRun.brand_id == brand_id,
            )
        )
    ).scalar_one_or_none()
    if not run:
        raise ValueError("Run not found")
    run.status = "rolled_back"
    run.output_payload_json = {**(run.output_payload_json or {}), "rollback_marked_at": _utc_iso()}
    await db.flush()
    return _run_out(run)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def list_runs(db: AsyncSession, brand_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AutomationExecutionRun)
                .where(AutomationExecutionRun.brand_id == brand_id)
                .order_by(AutomationExecutionRun.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_run_out(r) for r in rows]


async def open_blocker_escalation(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    blocker_category: str,
    severity: str,
    title: str,
    summary: str,
    exact_operator_steps: list[dict[str, Any]],
    linked_run_id: uuid.UUID | None = None,
    risk_flags_json: dict | None = None,
    cost_exposure_json: dict | None = None,
    enqueue_notification: bool = True,
) -> dict[str, Any]:
    if not exact_operator_steps or not isinstance(exact_operator_steps, list):
        raise ValueError("exact_operator_steps must be a non-empty list")
    ordered = []
    for i, step in enumerate(exact_operator_steps):
        if not isinstance(step, dict):
            raise ValueError("each step must be an object")
        entry = dict(step)
        entry.setdefault("order", i + 1)
        ordered.append(entry)

    b = ExecutionBlockerEscalation(
        brand_id=brand_id,
        blocker_category=blocker_category,
        severity=severity,
        title=title[:500],
        summary=summary,
        exact_operator_steps_json={"steps": ordered},
        linked_run_id=linked_run_id,
        risk_flags_json=risk_flags_json,
        cost_exposure_json=cost_exposure_json,
        resolution_status="open",
    )
    db.add(b)
    await db.flush()

    if enqueue_notification:
        now = _utc_iso()
        payload = {
            "kind": "execution_blocker_escalation",
            "blocker_id": str(b.id),
            "title": b.title,
            "summary": b.summary,
            "severity": b.severity,
            "category": b.blocker_category,
            "steps_preview": ordered[:3],
            "detail_url": f"/dashboard/autonomous-execution?brand={brand_id}",
        }
        db.add(
            NotificationDelivery(
                brand_id=brand_id,
                alert_id=None,
                channel="in_app",
                recipient=None,
                payload=payload,
                status="pending",
                attempts=0,
            )
        )
        b.notification_enqueued_at = now
        await db.flush()

    return _blocker_out(b)


async def list_blockers(db: AsyncSession, brand_id: uuid.UUID, limit: int = 100) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ExecutionBlockerEscalation)
                .where(
                    ExecutionBlockerEscalation.brand_id == brand_id,
                    ExecutionBlockerEscalation.is_active.is_(True),
                )
                .order_by(ExecutionBlockerEscalation.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_blocker_out(x) for x in rows]


async def acknowledge_blocker(
    db: AsyncSession, brand_id: uuid.UUID, blocker_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    b = (
        await db.execute(
            select(ExecutionBlockerEscalation).where(
                ExecutionBlockerEscalation.id == blocker_id,
                ExecutionBlockerEscalation.brand_id == brand_id,
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise ValueError("Blocker not found")
    if b.resolution_status == "open":
        b.resolution_status = "acknowledged"
        b.resolved_by_user_id = user_id
    await db.flush()
    return _blocker_out(b)


async def resolve_blocker(
    db: AsyncSession,
    brand_id: uuid.UUID,
    blocker_id: uuid.UUID,
    user_id: uuid.UUID,
    resolution_notes: str | None,
) -> dict[str, Any]:
    b = (
        await db.execute(
            select(ExecutionBlockerEscalation).where(
                ExecutionBlockerEscalation.id == blocker_id,
                ExecutionBlockerEscalation.brand_id == brand_id,
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise ValueError("Blocker not found")
    b.resolution_status = "resolved"
    b.resolved_at = _utc_iso()
    b.resolved_by_user_id = user_id
    b.resolution_notes = resolution_notes
    await db.flush()
    return _blocker_out(b)
