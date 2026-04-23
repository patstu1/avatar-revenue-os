"""Workflow Builder Service — create, advance, approve, reject, override."""
from __future__ import annotations
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.workflow_builder import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowInstanceStep,
    WorkflowApproval, WorkflowRejection, WorkflowOverride, WorkflowTemplate,
)
from packages.scoring.workflow_engine import evaluate_workflow_step, process_approval, process_rejection, process_override, apply_template


async def create_workflow(db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]) -> WorkflowDefinition:
    wf = WorkflowDefinition(organization_id=org_id, brand_id=data.get("brand_id"), workflow_name=data["workflow_name"], workflow_type=data["workflow_type"], scope_type=data.get("scope_type", "org"), description=data.get("description"))
    db.add(wf); await db.flush()
    for s in data.get("steps", []):
        db.add(WorkflowStep(definition_id=wf.id, step_order=s["step_order"], step_name=s["step_name"], step_type=s["step_type"], required_role=s.get("required_role"), required_action=s.get("required_action", "approve"), auto_advance=s.get("auto_advance", False)))
    await db.flush()
    return wf


async def create_from_template(db: AsyncSession, org_id: uuid.UUID, template_key: str, brand_id: uuid.UUID = None) -> WorkflowDefinition:
    tmpl = apply_template(template_key)
    if not tmpl:
        raise ValueError(f"Unknown template: {template_key}")
    return await create_workflow(db, org_id, {"workflow_name": f"{template_key} workflow", "workflow_type": tmpl["workflow_type"], "brand_id": brand_id, "steps": tmpl["steps"]})


async def start_instance(db: AsyncSession, definition_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID, brand_id: uuid.UUID = None, initiated_by: uuid.UUID = None) -> WorkflowInstance:
    steps = list((await db.execute(select(WorkflowStep).where(WorkflowStep.definition_id == definition_id, WorkflowStep.is_active.is_(True)).order_by(WorkflowStep.step_order))).scalars().all())
    inst = WorkflowInstance(definition_id=definition_id, brand_id=brand_id, resource_type=resource_type, resource_id=resource_id, current_step_order=1, status="in_progress", initiated_by=initiated_by)
    db.add(inst); await db.flush()
    for s in steps:
        db.add(WorkflowInstanceStep(instance_id=inst.id, step_id=s.id, step_order=s.step_order, status="pending" if s.step_order > 1 else "awaiting_action"))
    await db.flush()
    return inst


async def approve_step(db: AsyncSession, instance_id: uuid.UUID, user_id: uuid.UUID, user_role: str, notes: str = "") -> dict[str, Any]:
    inst = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == instance_id))).scalar_one_or_none()
    if not inst or inst.status != "in_progress":
        return {"success": False, "reason": "Instance not found or not in progress"}

    steps = list((await db.execute(select(WorkflowStep).where(WorkflowStep.definition_id == inst.definition_id, WorkflowStep.is_active.is_(True)).order_by(WorkflowStep.step_order))).scalars().all())
    step_dicts = [{"step_order": s.step_order, "step_name": s.step_name, "step_type": s.step_type, "required_role": s.required_role, "required_action": s.required_action} for s in steps]
    inst_dict = {"current_step_order": inst.current_step_order, "status": inst.status}

    eval_result = evaluate_workflow_step(inst_dict, step_dicts, user_role)
    if not eval_result.get("can_act"):
        return {"success": False, "reason": eval_result.get("reason", "Cannot act")}

    current_step = next((s for s in steps if s.step_order == inst.current_step_order), None)
    if current_step:
        db.add(WorkflowApproval(instance_id=instance_id, step_id=current_step.id, approved_by=user_id, notes=notes))
        ist = (await db.execute(select(WorkflowInstanceStep).where(WorkflowInstanceStep.instance_id == instance_id, WorkflowInstanceStep.step_order == inst.current_step_order))).scalar_one_or_none()
        if ist:
            ist.status = "approved"; ist.acted_by = user_id

    result = process_approval(inst_dict, step_dicts)
    if result["action"] == "advance":
        inst.current_step_order = result["next_step_order"]
        nist = (await db.execute(select(WorkflowInstanceStep).where(WorkflowInstanceStep.instance_id == instance_id, WorkflowInstanceStep.step_order == result["next_step_order"]))).scalar_one_or_none()
        if nist:
            nist.status = "awaiting_action"
    else:
        inst.status = "completed"

    await db.flush()
    return {"success": True, **result}


async def reject_step(db: AsyncSession, instance_id: uuid.UUID, user_id: uuid.UUID, reason: str) -> dict[str, Any]:
    inst = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == instance_id))).scalar_one_or_none()
    if not inst:
        return {"success": False, "reason": "Not found"}
    current_step = (await db.execute(select(WorkflowStep).where(WorkflowStep.definition_id == inst.definition_id, WorkflowStep.step_order == inst.current_step_order))).scalar_one_or_none()
    if current_step:
        db.add(WorkflowRejection(instance_id=instance_id, step_id=current_step.id, rejected_by=user_id, reason=reason))
    inst.status = "rejected"; inst.current_step_order = 1
    await db.flush()
    return {"success": True, "action": "rollback", "status": "rejected"}


async def override_workflow(db: AsyncSession, instance_id: uuid.UUID, user_id: uuid.UUID, reason: str) -> dict[str, Any]:
    inst = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == instance_id))).scalar_one_or_none()
    if not inst:
        return {"success": False}
    db.add(WorkflowOverride(instance_id=instance_id, overridden_by=user_id, reason=reason))
    inst.status = "completed"
    await db.flush()
    return {"success": True, "action": "override_complete", "status": "completed"}


async def list_definitions(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.organization_id == org_id, WorkflowDefinition.is_active.is_(True)))).scalars().all())

async def list_instances(db: AsyncSession, org_id: uuid.UUID, status: str = None) -> list:
    q = select(WorkflowInstance).join(WorkflowDefinition).where(WorkflowDefinition.organization_id == org_id, WorkflowInstance.is_active.is_(True))
    if status:
        q = q.where(WorkflowInstance.status == status)
    return list((await db.execute(q.order_by(WorkflowInstance.created_at.desc()).limit(50))).scalars().all())

async def list_approvals(db: AsyncSession, instance_id: uuid.UUID) -> list:
    return list((await db.execute(select(WorkflowApproval).where(WorkflowApproval.instance_id == instance_id))).scalars().all())

async def list_rejections(db: AsyncSession, instance_id: uuid.UUID) -> list:
    return list((await db.execute(select(WorkflowRejection).where(WorkflowRejection.instance_id == instance_id))).scalars().all())

async def get_workflow_status(db: AsyncSession, resource_type: str, resource_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: check if a resource has a pending workflow."""
    inst = (await db.execute(select(WorkflowInstance).where(WorkflowInstance.resource_type == resource_type, WorkflowInstance.resource_id == resource_id, WorkflowInstance.is_active.is_(True)).order_by(WorkflowInstance.created_at.desc()).limit(1))).scalar_one_or_none()
    if not inst:
        return {"has_workflow": False, "status": "no_workflow"}
    return {"has_workflow": True, "status": inst.status, "current_step": inst.current_step_order, "instance_id": str(inst.id)}
