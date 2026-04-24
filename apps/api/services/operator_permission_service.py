"""Operator Permission Matrix Service — seed, evaluate, enforce, persist."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.operator_permission_matrix import (
    ActionExecutionMode,
    AutonomyActionPolicy,
    OperatorPermissionMatrix,
)
from packages.scoring.operator_permission_engine import (
    can_execute_autonomously,
    evaluate_override_eligibility,
    seed_default_matrix,
)


async def seed_matrix(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    existing = list((await db.execute(select(OperatorPermissionMatrix).where(OperatorPermissionMatrix.organization_id == org_id, OperatorPermissionMatrix.is_active.is_(True)))).scalars().all())
    existing_actions = {m.action_class for m in existing}
    created = 0
    for row in seed_default_matrix(str(org_id)):
        if row["action_class"] not in existing_actions:
            db.add(OperatorPermissionMatrix(organization_id=org_id, action_class=row["action_class"], autonomy_mode=row["autonomy_mode"], approval_role=row["approval_role"], override_allowed=row["override_allowed"], override_role=row["override_role"], explanation=row["explanation"]))
            created += 1
    await db.flush()
    return {"rows_created": created, "status": "completed"}


async def check_action(db: AsyncSession, org_id: uuid.UUID, action_class: str) -> dict[str, Any]:
    matrix = list((await db.execute(select(OperatorPermissionMatrix).where(OperatorPermissionMatrix.organization_id == org_id, OperatorPermissionMatrix.is_active.is_(True)))).scalars().all())
    policies = list((await db.execute(select(AutonomyActionPolicy).where(AutonomyActionPolicy.organization_id == org_id, AutonomyActionPolicy.is_active.is_(True)))).scalars().all())

    m_dicts = [{"action_class": m.action_class, "autonomy_mode": m.autonomy_mode, "approval_role": m.approval_role, "override_allowed": m.override_allowed, "override_role": m.override_role, "is_active": m.is_active} for m in matrix]
    p_dicts = [{"action_class": p.action_class, "default_mode": p.default_mode, "is_active": p.is_active} for p in policies]

    return can_execute_autonomously(action_class, m_dicts, p_dicts)


async def check_override(db: AsyncSession, org_id: uuid.UUID, action_class: str, user_role: str) -> dict[str, Any]:
    matrix = list((await db.execute(select(OperatorPermissionMatrix).where(OperatorPermissionMatrix.organization_id == org_id, OperatorPermissionMatrix.is_active.is_(True)))).scalars().all())
    m_dicts = [{"action_class": m.action_class, "autonomy_mode": m.autonomy_mode, "override_allowed": m.override_allowed, "override_role": m.override_role, "is_active": m.is_active} for m in matrix]
    return evaluate_override_eligibility(action_class, user_role, m_dicts, [])


async def list_matrix(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(OperatorPermissionMatrix).where(OperatorPermissionMatrix.organization_id == org_id, OperatorPermissionMatrix.is_active.is_(True)).order_by(OperatorPermissionMatrix.action_class))).scalars().all())


async def list_execution_modes(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(ActionExecutionMode).where(ActionExecutionMode.organization_id == org_id, ActionExecutionMode.is_active.is_(True)))).scalars().all())


async def get_autonomy_summary(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: autonomy summary for copilot/gatekeeper."""
    matrix = list((await db.execute(select(OperatorPermissionMatrix).where(OperatorPermissionMatrix.organization_id == org_id, OperatorPermissionMatrix.is_active.is_(True)))).scalars().all())
    by_mode: dict[str, int] = {}
    for m in matrix:
        by_mode[m.autonomy_mode] = by_mode.get(m.autonomy_mode, 0) + 1
    return {
        "total_actions": len(matrix),
        "by_mode": by_mode,
        "fully_autonomous": by_mode.get("fully_autonomous", 0),
        "guarded": by_mode.get("guarded_approval", 0),
        "manual_only": by_mode.get("manual_only", 0),
    }
