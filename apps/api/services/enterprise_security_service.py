"""Enterprise Security Service — RBAC, audit, compliance, data policies."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.enterprise_security import (
    AuditTrailEvent,
    ComplianceControlReport,
    EnterpriseAccessScope,
    EnterprisePermission,
    EnterpriseRole,
    ModelIsolationPolicy,
    RiskOverrideEvent,
    SensitiveDataPolicy,
)
from packages.scoring.enterprise_security_engine import (
    SYSTEM_ROLES,
    assess_compliance,
    evaluate_permission,
)


async def seed_system_roles(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    existing = list((await db.execute(select(EnterpriseRole).where(EnterpriseRole.organization_id == org_id, EnterpriseRole.is_system.is_(True)))).scalars().all())
    existing_names = {r.role_name for r in existing}
    created = 0
    for sr in SYSTEM_ROLES:
        if sr["role_name"] not in existing_names:
            db.add(EnterpriseRole(organization_id=org_id, role_name=sr["role_name"], role_level=sr["role_level"], description=sr["description"], is_system=True))
            created += 1
    await db.flush()
    return {"roles_created": created, "status": "completed"}


async def check_permission(db: AsyncSession, user_id: uuid.UUID, action: str) -> dict[str, Any]:
    scopes = list((await db.execute(select(EnterpriseAccessScope).where(EnterpriseAccessScope.user_id == user_id, EnterpriseAccessScope.is_active.is_(True)))).scalars().all())
    if not scopes:
        return {"allowed": True, "reason": "No enterprise scopes configured — default allow"}
    for s in scopes:
        role = (await db.execute(select(EnterpriseRole).where(EnterpriseRole.id == s.role_id))).scalar_one_or_none()
        if role:
            result = evaluate_permission(role.role_name, role.role_level, action)
            if result["allowed"]:
                return result
    return {"allowed": False, "reason": f"No role grants '{action}' permission"}


async def log_audit(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, action: str, resource_type: str, resource_id: uuid.UUID = None, detail: str = "", before: dict = None, after: dict = None) -> None:
    db.add(AuditTrailEvent(organization_id=org_id, user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id, detail=detail, before_state=before or {}, after_state=after or {}))
    await db.flush()


async def recompute_compliance(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    roles = list((await db.execute(select(EnterpriseRole).where(EnterpriseRole.organization_id == org_id))).scalars().all())
    scopes = list((await db.execute(select(EnterpriseAccessScope))).scalars().all())
    policies = list((await db.execute(select(SensitiveDataPolicy).where(SensitiveDataPolicy.organization_id == org_id))).scalars().all())
    isolation = list((await db.execute(select(ModelIsolationPolicy).where(ModelIsolationPolicy.organization_id == org_id))).scalars().all())
    audits = list((await db.execute(select(AuditTrailEvent).where(AuditTrailEvent.organization_id == org_id).limit(1))).scalars().all())

    state = {
        "rbac_configured": len(roles) > 0,
        "scopes_assigned": len(scopes) > 0,
        "data_policies_configured": len(policies) > 0,
        "audit_trail_active": len(audits) > 0,
        "model_isolation_set": len(isolation) > 0,
        "data_residency_set": any(i.data_residency for i in isolation),
        "erasure_capability": True,
        "consent_tracking": False,
    }

    await db.execute(delete(ComplianceControlReport).where(ComplianceControlReport.organization_id == org_id))
    total = 0
    for fw in ("gdpr", "soc2", "hipaa"):
        controls = assess_compliance(fw, state)
        for c in controls:
            db.add(ComplianceControlReport(organization_id=org_id, framework=c["framework"], control_id=c["control_id"], control_name=c["control_name"], status=c["status"], evidence=c["evidence"]))
            total += 1
    await db.flush()
    return {"rows_processed": total, "status": "completed"}


async def list_roles(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(EnterpriseRole).where(EnterpriseRole.organization_id == org_id, EnterpriseRole.is_active.is_(True)))).scalars().all())

async def list_permissions(db: AsyncSession, role_id: uuid.UUID) -> list:
    return list((await db.execute(select(EnterprisePermission).where(EnterprisePermission.role_id == role_id, EnterprisePermission.is_active.is_(True)))).scalars().all())

async def list_audit_trail(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(AuditTrailEvent).where(AuditTrailEvent.organization_id == org_id).order_by(AuditTrailEvent.created_at.desc()).limit(100))).scalars().all())

async def list_data_policies(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(SensitiveDataPolicy).where(SensitiveDataPolicy.organization_id == org_id, SensitiveDataPolicy.is_active.is_(True)))).scalars().all())

async def list_compliance_controls(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(ComplianceControlReport).where(ComplianceControlReport.organization_id == org_id, ComplianceControlReport.is_active.is_(True)))).scalars().all())

async def list_model_isolation(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(ModelIsolationPolicy).where(ModelIsolationPolicy.organization_id == org_id, ModelIsolationPolicy.is_active.is_(True)))).scalars().all())

async def list_risk_overrides(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(RiskOverrideEvent).where(RiskOverrideEvent.organization_id == org_id, RiskOverrideEvent.is_active.is_(True)))).scalars().all())
