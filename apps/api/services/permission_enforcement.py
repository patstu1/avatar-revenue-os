"""Framework-level permission enforcement — wraps autonomous actions."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.operator_permission_service import check_action

logger = logging.getLogger(__name__)

ACTION_MAP = {
    "publish_content": "content_publish",
    "auto_publish": "content_publish",
    "generate_content": "content_generation",
    "launch_campaign": "campaign_launch",
    "publish_landing_page": "landing_page_publish",
    "affiliate_link_deploy": "affiliate_deploy",
    "scale_burst": "scale_burst",
    "recovery_rollback": "recovery_rollback",
    "recovery_reroute": "recovery_reroute",
    "recovery_throttle": "recovery_throttle",
    "capital_rebalance": "capital_rebalance",
    "experiment_promote": "experiment_promote",
    "expansion_launch": "expansion_launch",
}


class PermissionDenied(Exception):
    """Raised when an action is blocked by the permission matrix."""

    def __init__(self, action: str, mode: str, reason: str):
        self.action = action
        self.mode = mode
        self.reason = reason
        super().__init__(f"Action '{action}' denied — mode={mode}: {reason}")


async def enforce_permission(db: AsyncSession, org_id: uuid.UUID, action_key: str) -> dict[str, Any]:
    """Check permission matrix for an action. Raises PermissionDenied if blocked.

    Returns the permission result dict with 'allowed' and 'mode' keys.
    The check_action() call returns the output of can_execute_autonomously(),
    which has: allowed, needs_approval, needs_notification, reason.
    """
    action_class = ACTION_MAP.get(action_key, action_key)
    result = await check_action(db, org_id, action_class)

    allowed = result.get("allowed", True)
    reason = result.get("reason", "")

    if not allowed and "manual" in reason.lower():
        mode = "manual_only"
        logger.warning("Permission BLOCKED: action=%s org=%s mode=%s", action_key, org_id, mode)
        raise PermissionDenied(action_key, mode, reason)

    if not allowed and result.get("needs_approval"):
        mode = "guarded_approval"
        logger.warning("Permission GUARDED: action=%s org=%s mode=%s", action_key, org_id, mode)
        raise PermissionDenied(action_key, mode, reason)

    mode = "autonomous_notify" if result.get("needs_notification") else "fully_autonomous"
    return {"allowed": True, "mode": mode, "action_class": action_class}
