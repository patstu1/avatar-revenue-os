"""DB-backed integration tests for Enterprise Workflow Builder."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.workflow_service import (
    approve_step,
    create_from_template,
    get_workflow_status,
    list_definitions,
    list_instances,
    override_workflow,
    reject_step,
    start_instance,
)
from packages.db.enums import UserRole
from packages.db.models.core import Organization, User
from packages.db.models.workflow_builder import (
    WorkflowInstance,
    WorkflowInstanceStep,
    WorkflowStep,
)


@pytest_asyncio.fixture
async def org_with_user(db_session: AsyncSession):
    slug = f"wf-{uuid.uuid4().hex[:6]}"
    org = Organization(name="WF Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    from apps.api.services.auth_service import hash_password
    user = User(organization_id=org.id, email=f"wf_{slug}@test.com", hashed_password=hash_password("test123"), full_name="WF User", role=UserRole.OPERATOR)
    db_session.add(user); await db_session.flush()
    return org, user


@pytest.mark.asyncio
async def test_create_from_template(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish")
    await db_session.commit()
    assert wf.workflow_type == "content_generation"
    steps = (await db_session.execute(select(WorkflowStep).where(WorkflowStep.definition_id == wf.id))).scalars().all()
    assert len(steps) == 3


@pytest.mark.asyncio
async def test_start_instance(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    resource_id = uuid.uuid4()
    inst = await start_instance(db_session, wf.id, "content_item", resource_id, initiated_by=user.id)
    await db_session.commit()
    assert inst.status == "in_progress"
    assert inst.current_step_order == 1
    ist_steps = (await db_session.execute(select(WorkflowInstanceStep).where(WorkflowInstanceStep.instance_id == inst.id))).scalars().all()
    assert len(ist_steps) == 3


@pytest.mark.asyncio
async def test_approve_advances(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    inst = await start_instance(db_session, wf.id, "content_item", uuid.uuid4(), initiated_by=user.id); await db_session.flush()

    r1 = await approve_step(db_session, inst.id, user.id, "generator", "Looks good")
    assert r1["success"] is True
    assert r1["action"] == "advance"
    await db_session.flush()

    refreshed = (await db_session.execute(select(WorkflowInstance).where(WorkflowInstance.id == inst.id))).scalar_one()
    assert refreshed.current_step_order == 2


@pytest.mark.asyncio
async def test_full_approval_completes(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    inst = await start_instance(db_session, wf.id, "content_item", uuid.uuid4(), initiated_by=user.id); await db_session.flush()

    await approve_step(db_session, inst.id, user.id, "super_admin"); await db_session.flush()
    await approve_step(db_session, inst.id, user.id, "super_admin"); await db_session.flush()
    r3 = await approve_step(db_session, inst.id, user.id, "super_admin"); await db_session.flush()
    assert r3["action"] == "complete"

    refreshed = (await db_session.execute(select(WorkflowInstance).where(WorkflowInstance.id == inst.id))).scalar_one()
    assert refreshed.status == "completed"


@pytest.mark.asyncio
async def test_rejection_rolls_back(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    inst = await start_instance(db_session, wf.id, "content_item", uuid.uuid4(), initiated_by=user.id); await db_session.flush()
    await approve_step(db_session, inst.id, user.id, "super_admin"); await db_session.flush()

    r = await reject_step(db_session, inst.id, user.id, "Needs revision")
    assert r["success"] is True
    assert r["status"] == "rejected"


@pytest.mark.asyncio
async def test_override_completes(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    inst = await start_instance(db_session, wf.id, "content_item", uuid.uuid4(), initiated_by=user.id); await db_session.flush()

    r = await override_workflow(db_session, inst.id, user.id, "Urgent publish needed")
    assert r["success"] is True
    assert r["status"] == "completed"


@pytest.mark.asyncio
async def test_wrong_role_blocked(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    inst = await start_instance(db_session, wf.id, "content_item", uuid.uuid4(), initiated_by=user.id); await db_session.flush()

    r = await approve_step(db_session, inst.id, user.id, "viewer")
    assert r["success"] is False


@pytest.mark.asyncio
async def test_get_workflow_status(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    rid = uuid.uuid4()
    await start_instance(db_session, wf.id, "content_item", rid, initiated_by=user.id); await db_session.commit()

    status = await get_workflow_status(db_session, "content_item", rid)
    assert status["has_workflow"] is True
    assert status["status"] == "in_progress"


@pytest.mark.asyncio
async def test_list_definitions(db_session, org_with_user):
    org, _ = org_with_user
    await create_from_template(db_session, org.id, "content_publish"); await db_session.commit()
    defs = await list_definitions(db_session, org.id)
    assert len(defs) >= 1


@pytest.mark.asyncio
async def test_list_instances(db_session, org_with_user):
    org, user = org_with_user
    wf = await create_from_template(db_session, org.id, "content_publish"); await db_session.flush()
    await start_instance(db_session, wf.id, "content_item", uuid.uuid4(), initiated_by=user.id); await db_session.commit()
    insts = await list_instances(db_session, org.id)
    assert len(insts) >= 1
