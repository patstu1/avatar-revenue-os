"""Operator Permission Matrix Engine — autonomy modes, policy eval, overrides. Pure functions."""
from __future__ import annotations

from typing import Any

ACTION_CLASSES = [
    "content_generation", "content_publish", "campaign_launch", "campaign_suppress",
    "scaling_output", "launch_account", "offer_switch", "affiliate_offer_switch",
    "email_send", "sms_send", "landing_page_publish", "budget_escalation",
    "provider_config_change", "rollback_action", "governance_override",
]

AUTONOMY_MODES = ["fully_autonomous", "autonomous_notify", "guarded_approval", "manual_only"]

DEFAULT_POLICIES = {
    "content_generation": {"mode": "fully_autonomous", "approval_role": None, "override_role": "brand_admin"},
    "content_publish": {"mode": "autonomous_notify", "approval_role": "brand_admin", "override_role": "org_admin"},
    "campaign_launch": {"mode": "guarded_approval", "approval_role": "brand_admin", "override_role": "org_admin"},
    "campaign_suppress": {"mode": "autonomous_notify", "approval_role": None, "override_role": "brand_admin"},
    "scaling_output": {"mode": "autonomous_notify", "approval_role": None, "override_role": "brand_admin"},
    "launch_account": {"mode": "guarded_approval", "approval_role": "org_admin", "override_role": "super_admin"},
    "offer_switch": {"mode": "autonomous_notify", "approval_role": None, "override_role": "brand_admin"},
    "affiliate_offer_switch": {"mode": "autonomous_notify", "approval_role": None, "override_role": "brand_admin"},
    "email_send": {"mode": "guarded_approval", "approval_role": "brand_admin", "override_role": "org_admin"},
    "sms_send": {"mode": "guarded_approval", "approval_role": "brand_admin", "override_role": "org_admin"},
    "landing_page_publish": {"mode": "guarded_approval", "approval_role": "brand_admin", "override_role": "org_admin"},
    "budget_escalation": {"mode": "guarded_approval", "approval_role": "org_admin", "override_role": "super_admin"},
    "provider_config_change": {"mode": "manual_only", "approval_role": "org_admin", "override_role": "super_admin"},
    "rollback_action": {"mode": "fully_autonomous", "approval_role": None, "override_role": "org_admin"},
    "governance_override": {"mode": "manual_only", "approval_role": "super_admin", "override_role": "super_admin"},
}


def evaluate_action_policy(action_class: str, matrix: list[dict[str, Any]], policies: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate whether an action is allowed and in what mode."""
    for m in matrix:
        if m.get("action_class") == action_class and m.get("is_active", True):
            return {"action_class": action_class, "mode": m["autonomy_mode"], "approval_role": m.get("approval_role"), "override_allowed": m.get("override_allowed", True), "override_role": m.get("override_role"), "source": "matrix"}

    for p in policies:
        if p.get("action_class") == action_class and p.get("is_active", True):
            return {"action_class": action_class, "mode": p["default_mode"], "approval_role": None, "override_allowed": True, "override_role": None, "source": "policy"}

    default = DEFAULT_POLICIES.get(action_class, {"mode": "guarded_approval", "approval_role": "org_admin", "override_role": "super_admin"})
    return {"action_class": action_class, "mode": default["mode"], "approval_role": default["approval_role"], "override_allowed": True, "override_role": default["override_role"], "source": "default"}


def can_execute_autonomously(action_class: str, matrix: list[dict], policies: list[dict]) -> dict[str, Any]:
    """Quick check: can the machine do this by itself?"""
    policy = evaluate_action_policy(action_class, matrix, policies)
    mode = policy["mode"]

    if mode == "fully_autonomous":
        return {"allowed": True, "needs_approval": False, "needs_notification": False, "reason": "Fully autonomous"}
    if mode == "autonomous_notify":
        return {"allowed": True, "needs_approval": False, "needs_notification": True, "reason": "Autonomous with notification"}
    if mode == "guarded_approval":
        return {"allowed": False, "needs_approval": True, "needs_notification": True, "reason": f"Requires approval from {policy.get('approval_role', 'admin')}"}
    return {"allowed": False, "needs_approval": True, "needs_notification": True, "reason": "Manual only — operator must execute"}


def evaluate_override_eligibility(action_class: str, user_role: str, matrix: list[dict], overrides: list[dict]) -> dict[str, Any]:
    """Check if a user can override the normal policy."""
    policy = evaluate_action_policy(action_class, matrix, [])
    if not policy.get("override_allowed"):
        return {"can_override": False, "reason": "Overrides disabled for this action"}

    required_role = policy.get("override_role", "super_admin")
    role_levels = {"super_admin": 100, "org_admin": 90, "brand_admin": 80, "approver": 60, "publisher": 55, "generator": 40, "viewer": 10}
    user_level = role_levels.get(user_role, 0)
    required_level = role_levels.get(required_role, 100)

    if user_level >= required_level:
        return {"can_override": True, "reason": f"Role {user_role} meets override requirement"}
    return {"can_override": False, "reason": f"Role {user_role} cannot override (requires {required_role})"}


def detect_policy_conflicts(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect conflicting policies for the same action class."""
    conflicts = []
    by_action: dict[str, list[dict]] = {}
    for m in matrix:
        ac = m.get("action_class", "")
        by_action.setdefault(ac, []).append(m)

    for ac, entries in by_action.items():
        active = [e for e in entries if e.get("is_active", True)]
        if len(active) > 1:
            modes = {e.get("autonomy_mode") for e in active}
            if len(modes) > 1:
                conflicts.append({"action_class": ac, "conflict": f"Multiple active entries with different modes: {modes}", "entries": len(active)})
    return conflicts


def seed_default_matrix(org_id: str) -> list[dict[str, Any]]:
    """Generate the default permission matrix for seeding."""
    rows = []
    for ac, policy in DEFAULT_POLICIES.items():
        rows.append({
            "organization_id": org_id,
            "action_class": ac,
            "autonomy_mode": policy["mode"],
            "approval_role": policy["approval_role"],
            "override_allowed": True,
            "override_role": policy["override_role"],
            "explanation": f"Default policy for {ac}",
        })
    return rows
