"""DB-backed integration tests for Operator Permission Matrix."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.core import Organization
from packages.db.models.operator_permission_matrix import OperatorPermissionMatrix
from apps.api.services.operator_permission_service import seed_matrix, check_action, check_override, list_matrix, get_autonomy_summary


@pytest_asyncio.fixture
async def org(db_session: AsyncSession):
    slug = f"opm-{uuid.uuid4().hex[:6]}"
    org = Organization(name="OPM Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_seed_matrix(db_session, org):
    result = await seed_matrix(db_session, org.id)
    await db_session.commit()
    assert result["rows_created"] == 15
    rows = (await db_session.execute(select(OperatorPermissionMatrix).where(OperatorPermissionMatrix.organization_id == org.id))).scalars().all()
    assert len(rows) == 15


@pytest.mark.asyncio
async def test_seed_idempotent(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    r2 = await seed_matrix(db_session, org.id); await db_session.commit()
    assert r2["rows_created"] == 0


@pytest.mark.asyncio
async def test_check_fully_autonomous(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    r = await check_action(db_session, org.id, "content_generation")
    assert r["allowed"] is True
    assert r["needs_approval"] is False


@pytest.mark.asyncio
async def test_check_guarded(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    r = await check_action(db_session, org.id, "campaign_launch")
    assert r["allowed"] is False
    assert r["needs_approval"] is True


@pytest.mark.asyncio
async def test_check_manual_only(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    r = await check_action(db_session, org.id, "governance_override")
    assert r["allowed"] is False


@pytest.mark.asyncio
async def test_override_check(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    r = await check_override(db_session, org.id, "content_publish", "org_admin")
    assert r["can_override"] is True


@pytest.mark.asyncio
async def test_override_blocked(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    r = await check_override(db_session, org.id, "governance_override", "viewer")
    assert r["can_override"] is False


@pytest.mark.asyncio
async def test_list_matrix(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    rows = await list_matrix(db_session, org.id)
    assert len(rows) == 15


@pytest.mark.asyncio
async def test_autonomy_summary(db_session, org):
    await seed_matrix(db_session, org.id); await db_session.commit()
    s = await get_autonomy_summary(db_session, org.id)
    assert s["total_actions"] == 15
    assert s["fully_autonomous"] >= 2
    assert s["manual_only"] >= 2
    assert sum(s["by_mode"].values()) == 15
