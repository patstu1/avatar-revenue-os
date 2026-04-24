"""Autonomous execution control plane — policy, gate preview, runs, blocker escalations."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.autonomous_execution import (
    AutomationExecutionPolicyOut,
    AutomationExecutionPolicyUpdate,
    AutomationExecutionRunCreate,
    AutomationExecutionRunOut,
    AutomationExecutionRunPatch,
    AutomationGatePreviewOut,
    BlockerResolveBody,
    ExecutionBlockerCreate,
    ExecutionBlockerEscalationOut,
)
from apps.api.services import autonomous_execution_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand
from packages.scoring.autonomous_execution_engine import AUTONOMOUS_LOOP_STEPS

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/automation-loop-steps", response_model=dict)
async def list_loop_steps(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return {"steps": list(AUTONOMOUS_LOOP_STEPS)}


@router.get(
    "/{brand_id}/automation-execution-policy",
    response_model=AutomationExecutionPolicyOut,
)
async def get_policy(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.get_policy(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put(
    "/{brand_id}/automation-execution-policy",
    response_model=AutomationExecutionPolicyOut,
)
async def put_policy(
    brand_id: uuid.UUID,
    body: AutomationExecutionPolicyUpdate,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        out = await svc.update_policy(
            db,
            brand_id,
            operating_mode=body.operating_mode,
            min_confidence_auto_execute=body.min_confidence_auto_execute,
            min_confidence_publish=body.min_confidence_publish,
            kill_switch_engaged=body.kill_switch_engaged,
            max_auto_cost_usd_per_action=body.max_auto_cost_usd_per_action,
            require_approval_above_cost_usd=body.require_approval_above_cost_usd,
            approval_gates_json=body.approval_gates_json,
            extra_policy_json=body.extra_policy_json,
        )
        await log_action(
            db,
            "autonomous_execution.policy_updated",
            organization_id=current_user.organization_id,
            brand_id=brand_id,
            user_id=current_user.id,
            actor_type="human",
            entity_type="automation_execution_policy",
            details=out,
        )
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/automation-gate-preview",
    response_model=AutomationGatePreviewOut,
)
async def gate_preview(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    loop_step: str = Query(...),
    confidence: float = Query(..., ge=0.0, le=1.0),
    estimated_cost_usd: Optional[float] = Query(None),
):
    """Read-only gate evaluation against current policy (no persistence)."""
    await _require_brand(brand_id, current_user, db)
    try:
        r = await svc.preview_gate(
            db,
            brand_id,
            loop_step=loop_step,
            confidence=confidence,
            estimated_cost_usd=estimated_cost_usd,
        )
        return AutomationGatePreviewOut(
            decision=r["decision"], reasons=r.get("reasons") or [], guardrail=r.get("guardrail")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{brand_id}/automation-execution-runs",
    response_model=list[AutomationExecutionRunOut],
)
async def list_runs(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_runs(db, brand_id, limit=limit)


@router.post(
    "/{brand_id}/automation-execution-runs",
    response_model=AutomationExecutionRunOut,
)
async def create_run(
    brand_id: uuid.UUID,
    body: AutomationExecutionRunCreate,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        out = await svc.create_execution_run(
            db,
            brand_id,
            loop_step=body.loop_step,
            status=body.status,
            confidence_score=body.confidence_score,
            input_payload_json=body.input_payload_json,
        )
        await log_action(
            db,
            "autonomous_execution.run_created",
            organization_id=current_user.organization_id,
            brand_id=brand_id,
            user_id=current_user.id,
            actor_type="human",
            entity_type="automation_execution_run",
            details={"run_id": out["id"], "loop_step": body.loop_step},
        )
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch(
    "/{brand_id}/automation-execution-runs/{run_id}",
    response_model=AutomationExecutionRunOut,
)
async def patch_run(
    brand_id: uuid.UUID,
    run_id: uuid.UUID,
    body: AutomationExecutionRunPatch,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.update_run_status(
            db,
            brand_id,
            run_id,
            status=body.status,
            output_payload_json=body.output_payload_json,
            blocked_reason=body.blocked_reason,
            error_message=body.error_message,
            approval_status=body.approval_status,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/{brand_id}/automation-execution-runs/{run_id}/rollback",
    response_model=AutomationExecutionRunOut,
)
async def rollback_run(
    brand_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        out = await svc.mark_run_rollback(db, brand_id, run_id)
        await log_action(
            db,
            "autonomous_execution.run_rollback",
            organization_id=current_user.organization_id,
            brand_id=brand_id,
            user_id=current_user.id,
            actor_type="human",
            entity_type="automation_execution_run",
            details={"run_id": str(run_id)},
        )
        return out
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/{brand_id}/execution-blocker-escalations",
    response_model=list[ExecutionBlockerEscalationOut],
)
async def list_blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_blockers(db, brand_id)


@router.post(
    "/{brand_id}/execution-blocker-escalations",
    response_model=ExecutionBlockerEscalationOut,
)
async def create_blocker(
    brand_id: uuid.UUID,
    body: ExecutionBlockerCreate,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        lid = uuid.UUID(body.linked_run_id) if body.linked_run_id else None
        out = await svc.open_blocker_escalation(
            db,
            brand_id,
            blocker_category=body.blocker_category,
            severity=body.severity,
            title=body.title,
            summary=body.summary,
            exact_operator_steps=body.exact_operator_steps_json,
            linked_run_id=lid,
            risk_flags_json=body.risk_flags_json,
            cost_exposure_json=body.cost_exposure_json,
            enqueue_notification=body.enqueue_notification,
        )
        await log_action(
            db,
            "autonomous_execution.blocker_opened",
            organization_id=current_user.organization_id,
            brand_id=brand_id,
            user_id=current_user.id,
            actor_type="human",
            entity_type="execution_blocker_escalation",
            details={"blocker_id": out["id"], "category": body.blocker_category},
        )
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/{brand_id}/execution-blocker-escalations/{blocker_id}/acknowledge",
    response_model=ExecutionBlockerEscalationOut,
)
async def acknowledge_blocker(
    brand_id: uuid.UUID,
    blocker_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.acknowledge_blocker(db, brand_id, blocker_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/{brand_id}/execution-blocker-escalations/{blocker_id}/resolve",
    response_model=ExecutionBlockerEscalationOut,
)
async def resolve_blocker(
    brand_id: uuid.UUID,
    blocker_id: uuid.UUID,
    body: BlockerResolveBody,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        out = await svc.resolve_blocker(db, brand_id, blocker_id, current_user.id, body.resolution_notes)
        await log_action(
            db,
            "autonomous_execution.blocker_resolved",
            organization_id=current_user.organization_id,
            brand_id=brand_id,
            user_id=current_user.id,
            actor_type="human",
            entity_type="execution_blocker_escalation",
            details={"blocker_id": str(blocker_id)},
        )
        return out
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
