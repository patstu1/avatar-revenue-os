"""GM write-tool shared helpers (Batch 7B).

Every ``/gm/*`` write endpoint wraps exactly one existing canonical
service function (reply_draft_actions, proposals_service,
stage_controller, stripe_billing_service). The wrapper layer's
responsibilities:

  1. Enforce doctrine: classify_action on the intent. If result is
     ESCALATE, open a GMEscalation and refuse the mutation. If result
     is APPROVAL_REQUIRED, the operator calling the tool IS exercising
     that approval — proceed. Never silently downgrade APPROVAL_REQUIRED
     to AUTO.

  2. Write audit trail: one OperatorAction row per mutation (source
     module = "gm_write"), keyed to the entity being acted on.

  3. Emit canonical GM-domain SystemEvent: ``gm.write.<tool_name>``.

  4. Org-scope every call. Reject cross-org access with HTTP 403.

Nothing in this module duplicates business logic from the wrapped
services. The single source of truth for each business rule remains
in its canonical service.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.core import User
from packages.db.models.system_events import OperatorAction

logger = structlog.get_logger()


async def audit_gm_write(
    db: AsyncSession,
    *,
    actor: User,
    tool_name: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID],
    decision: str,
    action_class: str,
    details: Optional[dict] = None,
    severity: str = "info",
) -> OperatorAction:
    """Write the audit row + emit the gm.write event.

    Exactly one of these per GM write-tool invocation, regardless of
    outcome (success or refused). The audit trail is the doctrinal
    evidence that the mutation happened (or was refused) and who did it.
    """
    payload = {
        "tool_name": tool_name,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "decision": decision,
        "action_class": action_class,
        "actor_email": actor.email,
        "actor_id": str(actor.id),
        **(details or {}),
    }

    action_row = OperatorAction(
        organization_id=actor.organization_id,
        action_type=f"gm.write.{tool_name}",
        title=f"GM {tool_name} — {decision}",
        description=(
            f"{actor.email} invoked GM tool {tool_name}. "
            f"Action class: {action_class}. Decision: {decision}."
        ),
        priority="medium",
        category="gm_operating",
        entity_type=entity_type,
        entity_id=entity_id,
        source_module="gm_write",
        action_payload=payload,
        status="completed" if decision == "executed" else "recorded",
        completed_at=(
            datetime.now(timezone.utc) if decision == "executed" else None
        ),
    )
    db.add(action_row)
    await db.flush()

    await emit_event(
        db,
        domain="gm",
        event_type=f"gm.write.{tool_name}",
        summary=f"GM {tool_name} by {actor.email}: {decision}",
        org_id=actor.organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        new_state=decision,
        actor_type="operator",
        actor_id=str(actor.id),
        severity=severity,
        details=payload,
    )

    logger.info(
        f"gm_write.{tool_name}",
        actor=actor.email,
        tool=tool_name,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        decision=decision,
        action_class=action_class,
    )
    return action_row


def forbid_escalation_as_mutation(
    *,
    tool_name: str,
    action_class: str,
) -> None:
    """Raise if the caller's intent classified as ESCALATE — that means
    the caller should have opened an escalation instead of mutating.
    The caller handles HTTP shape; this only enforces the rule.
    """
    from apps.api.services.gm_doctrine import ACTION_CLASS_ESCALATE
    if action_class == ACTION_CLASS_ESCALATE:
        raise PermissionError(
            f"GM tool {tool_name} refused: action classified as "
            f"{ACTION_CLASS_ESCALATE}. Open a GMEscalation instead."
        )
