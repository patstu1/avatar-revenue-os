"""DB-backed integration tests for Enterprise Security + Compliance."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.core import Organization, User
from packages.db.models.enterprise_security import EnterpriseRole, EnterpriseAccessScope, AuditTrailEvent, ComplianceControlReport, SensitiveDataPolicy
from packages.db.enums import UserRole
from apps.api.services.enterprise_security_service import seed_system_roles, check_permission, log_audit, recompute_compliance, list_roles, list_audit_trail, list_compliance_controls


@pytest_asyncio.fixture
async def org_with_user(db_session: AsyncSession):
    slug = f"es-{uuid.uuid4().hex[:6]}"
    org = Organization(name="ES Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    from apps.api.services.auth_service import hash_password
    user = User(organization_id=org.id, email=f"es_{slug}@test.com", hashed_password=hash_password("test123"), full_name="ES User", role=UserRole.OPERATOR)
    db_session.add(user); await db_session.flush()
    return org, user


@pytest.mark.asyncio
async def test_seed_system_roles(db_session, org_with_user):
    org, _ = org_with_user
    result = await seed_system_roles(db_session, org.id)
    await db_session.commit()
    assert result["roles_created"] == 8
    roles = (await db_session.execute(select(EnterpriseRole).where(EnterpriseRole.organization_id == org.id))).scalars().all()
    assert len(roles) == 8
    names = {r.role_name for r in roles}
    assert "super_admin" in names and "viewer" in names


@pytest.mark.asyncio
async def test_seed_idempotent(db_session, org_with_user):
    org, _ = org_with_user
    await seed_system_roles(db_session, org.id); await db_session.commit()
    r2 = await seed_system_roles(db_session, org.id); await db_session.commit()
    assert r2["roles_created"] == 0


@pytest.mark.asyncio
async def test_check_permission_default_allow(db_session, org_with_user):
    _, user = org_with_user
    result = await check_permission(db_session, user.id, "generate")
    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_check_permission_with_scope(db_session, org_with_user):
    org, user = org_with_user
    await seed_system_roles(db_session, org.id); await db_session.flush()
    viewer_role = (await db_session.execute(select(EnterpriseRole).where(EnterpriseRole.organization_id == org.id, EnterpriseRole.role_name == "viewer"))).scalar_one()
    db_session.add(EnterpriseAccessScope(user_id=user.id, scope_type="org", role_id=viewer_role.id))
    await db_session.flush()
    result = await check_permission(db_session, user.id, "generate")
    assert result["allowed"] is False
    result_view = await check_permission(db_session, user.id, "view")
    assert result_view["allowed"] is True


@pytest.mark.asyncio
async def test_log_audit(db_session, org_with_user):
    org, user = org_with_user
    await log_audit(db_session, org.id, user.id, "publish", "content_item", detail="Published item X")
    await db_session.commit()
    events = (await db_session.execute(select(AuditTrailEvent).where(AuditTrailEvent.organization_id == org.id))).scalars().all()
    assert len(events) == 1
    assert events[0].action == "publish"


@pytest.mark.asyncio
async def test_recompute_compliance(db_session, org_with_user):
    org, _ = org_with_user
    await seed_system_roles(db_session, org.id); await db_session.flush()
    result = await recompute_compliance(db_session, org.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 14
    controls = (await db_session.execute(select(ComplianceControlReport).where(ComplianceControlReport.organization_id == org.id))).scalars().all()
    assert len(controls) >= 14
    frameworks = {c.framework for c in controls}
    assert "gdpr" in frameworks and "soc2" in frameworks and "hipaa" in frameworks


@pytest.mark.asyncio
async def test_list_roles(db_session, org_with_user):
    org, _ = org_with_user
    await seed_system_roles(db_session, org.id); await db_session.commit()
    roles = await list_roles(db_session, org.id)
    assert len(roles) == 8


@pytest.mark.asyncio
async def test_list_audit_trail(db_session, org_with_user):
    org, user = org_with_user
    await log_audit(db_session, org.id, user.id, "test_action", "test_resource"); await db_session.commit()
    trail = await list_audit_trail(db_session, org.id)
    assert len(trail) >= 1


@pytest.mark.asyncio
async def test_list_compliance(db_session, org_with_user):
    org, _ = org_with_user
    await seed_system_roles(db_session, org.id); await db_session.flush()
    await recompute_compliance(db_session, org.id); await db_session.commit()
    controls = await list_compliance_controls(db_session, org.id)
    assert len(controls) >= 14


def test_enterprise_security_worker_registered():
    from workers.celery_app import app
    import workers.enterprise_security_worker.tasks  # noqa: F401
    assert "workers.enterprise_security_worker.tasks.recompute_compliance" in app.tasks
