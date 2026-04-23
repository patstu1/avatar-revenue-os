"""Enterprise Workflow Engine — evaluate, route, gate, escalate. Pure functions."""
from __future__ import annotations
from typing import Any, Optional

WORKFLOW_TYPES = ["content_generation", "landing_page_publish", "campaign_launch", "affiliate_rollout", "provider_change", "risk_override", "governance_exception"]
STEP_TYPES = ["draft_review", "compliance_review", "brand_review", "legal_review", "publish_approval", "escalation", "auto_check"]

BUILT_IN_TEMPLATES = {
    "content_publish": {
        "workflow_type": "content_generation",
        "steps": [
            {"step_order": 1, "step_name": "Draft Review", "step_type": "draft_review", "required_role": "generator", "required_action": "approve"},
            {"step_order": 2, "step_name": "Brand Review", "step_type": "brand_review", "required_role": "brand_admin", "required_action": "approve"},
            {"step_order": 3, "step_name": "Publish Approval", "step_type": "publish_approval", "required_role": "publisher", "required_action": "approve"},
        ],
    },
    "campaign_launch": {
        "workflow_type": "campaign_launch",
        "steps": [
            {"step_order": 1, "step_name": "Campaign Review", "step_type": "draft_review", "required_role": "brand_admin", "required_action": "approve"},
            {"step_order": 2, "step_name": "Compliance Check", "step_type": "compliance_review", "required_role": "approver", "required_action": "approve"},
            {"step_order": 3, "step_name": "Launch Approval", "step_type": "publish_approval", "required_role": "org_admin", "required_action": "approve"},
        ],
    },
    "risk_override": {
        "workflow_type": "risk_override",
        "steps": [
            {"step_order": 1, "step_name": "Override Request", "step_type": "draft_review", "required_role": "brand_admin", "required_action": "approve"},
            {"step_order": 2, "step_name": "Legal Review", "step_type": "legal_review", "required_role": "org_admin", "required_action": "approve"},
            {"step_order": 3, "step_name": "Final Approval", "step_type": "escalation", "required_role": "super_admin", "required_action": "approve"},
        ],
    },
}


def evaluate_workflow_step(instance: dict[str, Any], steps: list[dict[str, Any]], user_role: str) -> dict[str, Any]:
    """Evaluate whether the current step can be acted on by the user."""
    current_order = instance.get("current_step_order", 1)
    current_step = None
    for s in steps:
        if s.get("step_order") == current_order:
            current_step = s
            break

    if not current_step:
        return {"can_act": False, "reason": "No step found at current order", "status": "error"}

    required_role = current_step.get("required_role")
    if required_role and user_role != required_role and user_role not in ("super_admin", "org_admin"):
        return {"can_act": False, "reason": f"Step requires role '{required_role}', user has '{user_role}'", "step": current_step}

    return {"can_act": True, "step": current_step, "required_action": current_step.get("required_action", "approve")}


def get_next_step(steps: list[dict[str, Any]], current_order: int) -> Optional[dict[str, Any]]:
    """Get the next step in the workflow."""
    for s in sorted(steps, key=lambda x: x.get("step_order", 0)):
        if s.get("step_order", 0) > current_order:
            return s
    return None


def process_approval(instance: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Process an approval — advance to next step or complete."""
    current_order = instance.get("current_step_order", 1)
    next_step = get_next_step(steps, current_order)

    if next_step:
        return {"action": "advance", "next_step_order": next_step["step_order"], "next_step_name": next_step["step_name"], "status": "in_progress"}
    return {"action": "complete", "status": "completed"}


def process_rejection(instance: dict[str, Any]) -> dict[str, Any]:
    """Process a rejection — roll back to step 1."""
    return {"action": "rollback", "rollback_to": 1, "status": "rejected"}


def process_override(instance: dict[str, Any]) -> dict[str, Any]:
    """Process an override — skip to completion."""
    return {"action": "override_complete", "status": "completed"}


def apply_template(template_key: str) -> Optional[dict[str, Any]]:
    """Return a built-in template's definition."""
    return BUILT_IN_TEMPLATES.get(template_key)


def get_pending_actions(instances: list[dict[str, Any]], steps_map: dict[str, list[dict]], user_role: str) -> list[dict[str, Any]]:
    """Get all pending actions across workflow instances for a user."""
    pending = []
    for inst in instances:
        if inst.get("status") != "in_progress":
            continue
        def_id = str(inst.get("definition_id", ""))
        steps = steps_map.get(def_id, [])
        eval_result = evaluate_workflow_step(inst, steps, user_role)
        if eval_result.get("can_act"):
            pending.append({"instance_id": inst.get("id"), "resource_type": inst.get("resource_type"), "resource_id": inst.get("resource_id"), "step_name": eval_result["step"]["step_name"], "required_action": eval_result["required_action"]})
    return pending
