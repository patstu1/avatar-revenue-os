"""Enterprise Security Engine — RBAC eval, scope enforce, data policy, compliance. Pure functions."""
from __future__ import annotations

from typing import Any

SYSTEM_ROLES = [
    {"role_name": "super_admin", "role_level": 100, "description": "Full system access"},
    {"role_name": "org_admin", "role_level": 90, "description": "Organization-wide admin"},
    {"role_name": "brand_admin", "role_level": 80, "description": "Brand-level admin"},
    {"role_name": "analyst", "role_level": 50, "description": "Read analytics and reports"},
    {"role_name": "generator", "role_level": 40, "description": "Create and generate content"},
    {"role_name": "approver", "role_level": 60, "description": "Approve content and campaigns"},
    {"role_name": "publisher", "role_level": 55, "description": "Publish approved content"},
    {"role_name": "viewer", "role_level": 10, "description": "Read-only access"},
]

SCOPE_TYPES = ["org", "business_unit", "client", "brand", "market", "language", "campaign", "action"]

ACTION_PERMISSIONS = {
    "generate": {"min_level": 40, "roles": ["super_admin", "org_admin", "brand_admin", "generator"]},
    "approve": {"min_level": 60, "roles": ["super_admin", "org_admin", "brand_admin", "approver"]},
    "publish": {"min_level": 55, "roles": ["super_admin", "org_admin", "brand_admin", "publisher"]},
    "admin": {"min_level": 80, "roles": ["super_admin", "org_admin", "brand_admin"]},
    "view": {"min_level": 10, "roles": ["super_admin", "org_admin", "brand_admin", "analyst", "generator", "approver", "publisher", "viewer"]},
    "delete": {"min_level": 90, "roles": ["super_admin", "org_admin"]},
    "configure": {"min_level": 80, "roles": ["super_admin", "org_admin", "brand_admin"]},
    "override_risk": {"min_level": 90, "roles": ["super_admin", "org_admin"]},
}

DATA_CLASSES = ["public", "internal", "confidential", "restricted", "pii", "financial", "health"]

COMPLIANCE_FRAMEWORKS = {
    "gdpr": [
        {"control_id": "GDPR-1", "control_name": "Data minimization", "check": "data_policies_configured"},
        {"control_id": "GDPR-2", "control_name": "Right to erasure support", "check": "erasure_capability"},
        {"control_id": "GDPR-3", "control_name": "Consent tracking", "check": "consent_tracking"},
        {"control_id": "GDPR-4", "control_name": "Data processing records", "check": "audit_trail_active"},
        {"control_id": "GDPR-5", "control_name": "Cross-border transfer controls", "check": "data_residency_set"},
    ],
    "soc2": [
        {"control_id": "SOC2-CC6.1", "control_name": "Logical access controls", "check": "rbac_configured"},
        {"control_id": "SOC2-CC6.2", "control_name": "Access provisioning", "check": "scopes_assigned"},
        {"control_id": "SOC2-CC7.1", "control_name": "Change management", "check": "audit_trail_active"},
        {"control_id": "SOC2-CC7.2", "control_name": "System monitoring", "check": "audit_trail_active"},
        {"control_id": "SOC2-CC8.1", "control_name": "Data classification", "check": "data_policies_configured"},
    ],
    "hipaa": [
        {"control_id": "HIPAA-164.312a", "control_name": "Access control", "check": "rbac_configured"},
        {"control_id": "HIPAA-164.312b", "control_name": "Audit controls", "check": "audit_trail_active"},
        {"control_id": "HIPAA-164.312c", "control_name": "Integrity controls", "check": "data_policies_configured"},
        {"control_id": "HIPAA-164.312e", "control_name": "Transmission security", "check": "model_isolation_set"},
    ],
}


def evaluate_permission(user_role: str, user_level: int, action: str) -> dict[str, Any]:
    """Check if a user with given role/level can perform an action."""
    perm = ACTION_PERMISSIONS.get(action)
    if not perm:
        return {"allowed": False, "reason": f"Unknown action: {action}"}
    if user_level >= perm["min_level"]:
        return {"allowed": True, "reason": f"Level {user_level} meets minimum {perm['min_level']}"}
    if user_role in perm["roles"]:
        return {"allowed": True, "reason": f"Role {user_role} is authorized for {action}"}
    return {"allowed": False, "reason": f"Role {user_role} (level {user_level}) cannot perform {action} (requires level {perm['min_level']})"}


def evaluate_scope(user_scopes: list[dict[str, Any]], resource_scope_type: str, resource_scope_id: str) -> dict[str, Any]:
    """Check if user has access to a specific scope."""
    for s in user_scopes:
        if s.get("scope_type") == "org":
            return {"allowed": True, "reason": "Org-wide access"}
        if s.get("scope_type") == resource_scope_type and (str(s.get("scope_id", "")) == resource_scope_id or s.get("scope_id") is None):
            return {"allowed": True, "reason": f"Scope match: {resource_scope_type}"}
    return {"allowed": False, "reason": f"No scope access for {resource_scope_type}:{resource_scope_id}"}


def evaluate_sensitive_data(data_class: str, policies: list[dict[str, Any]], action: str) -> dict[str, Any]:
    """Check if an action is allowed under sensitive data policies."""
    for p in policies:
        if p.get("data_class") == data_class and p.get("is_active", True):
            if p.get("private_mode") and action in ("send_to_model", "generate"):
                model_restriction = p.get("model_restriction", "")
                return {"allowed": False, "reason": f"Private mode: data class '{data_class}' cannot use shared models. Required: {model_restriction}", "private_mode": True, "model_restriction": model_restriction}
            if p.get("training_leak_prevention") and action == "send_to_training":
                return {"allowed": False, "reason": f"Training leak prevention active for {data_class}", "training_blocked": True}
    return {"allowed": True, "reason": "No policy restrictions"}


def evaluate_model_isolation(provider_key: str, policies: list[dict[str, Any]]) -> dict[str, Any]:
    """Check model/provider isolation requirements."""
    for p in policies:
        if p.get("provider_key") == provider_key and p.get("is_active", True):
            if p.get("isolation_mode") == "dedicated":
                return {"isolation_required": True, "mode": "dedicated", "instance_id": p.get("dedicated_instance_id"), "data_residency": p.get("data_residency")}
            if p.get("isolation_mode") == "private":
                return {"isolation_required": True, "mode": "private", "data_residency": p.get("data_residency")}
    return {"isolation_required": False, "mode": "shared"}


def assess_compliance(framework: str, system_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Assess compliance controls for a framework."""
    controls = COMPLIANCE_FRAMEWORKS.get(framework, [])
    results = []
    for c in controls:
        check = c["check"]
        met = system_state.get(check, False)
        results.append({
            "framework": framework,
            "control_id": c["control_id"],
            "control_name": c["control_name"],
            "status": "met" if met else "not_met",
            "evidence": {"check": check, "value": met},
        })
    return results


def build_audit_event(user_id: str, action: str, resource_type: str, resource_id: str = "", detail: str = "", before: dict = None, after: dict = None) -> dict[str, Any]:
    return {"user_id": user_id, "action": action, "resource_type": resource_type, "resource_id": resource_id, "detail": detail, "before_state": before or {}, "after_state": after or {}}
