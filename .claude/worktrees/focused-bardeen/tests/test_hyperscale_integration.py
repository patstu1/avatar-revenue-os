"""DB-backed integration tests for Hyper-Scale Execution."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.core import Organization
from packages.db.models.hyperscale import ExecutionCapacityReport, ExecutionQueueSegment, ScaleHealthReport, UsageCeilingRule
from apps.api.services.hyperscale_service import recompute_capacity, list_capacity, list_segments, list_ceilings, list_scale_health, get_execution_health


@pytest_asyncio.fixture
async def org_with_segments(db_session: AsyncSession):
    slug = f"hs-{uuid.uuid4().hex[:6]}"
    org = Organization(name="HS Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()

    db_session.add(ExecutionQueueSegment(organization_id=org.id, segment_key="brand_a:gen:50", segment_type="generation", queue_depth=30, running_count=5, max_concurrency=20, priority=50))
    db_session.add(ExecutionQueueSegment(organization_id=org.id, segment_key="brand_b:gen:80", segment_type="generation", queue_depth=10, running_count=2, max_concurrency=15, priority=80))
    db_session.add(UsageCeilingRule(organization_id=org.id, ceiling_type="monthly_cost", max_value=500.0, current_value=350.0, period="monthly"))
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_recompute_capacity(db_session, org_with_segments):
    org = org_with_segments
    result = await recompute_capacity(db_session, org.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 3

    caps = (await db_session.execute(select(ExecutionCapacityReport).where(ExecutionCapacityReport.organization_id == org.id))).scalars().all()
    assert len(caps) == 1
    assert caps[0].total_queued == 40

    health = (await db_session.execute(select(ScaleHealthReport).where(ScaleHealthReport.organization_id == org.id))).scalars().all()
    assert len(health) == 1


@pytest.mark.asyncio
async def test_health_report_generated(db_session, org_with_segments):
    org = org_with_segments
    await recompute_capacity(db_session, org.id); await db_session.commit()
    health = (await db_session.execute(select(ScaleHealthReport).where(ScaleHealthReport.organization_id == org.id))).scalar_one()
    assert health.health_status in ("healthy", "busy", "degraded", "critical")
    assert health.queue_depth_total == 40


@pytest.mark.asyncio
async def test_list_capacity(db_session, org_with_segments):
    org = org_with_segments
    await recompute_capacity(db_session, org.id); await db_session.commit()
    caps = await list_capacity(db_session, org.id)
    assert len(caps) == 1


@pytest.mark.asyncio
async def test_list_segments(db_session, org_with_segments):
    org = org_with_segments
    segs = await list_segments(db_session, org.id)
    assert len(segs) == 2


@pytest.mark.asyncio
async def test_list_ceilings(db_session, org_with_segments):
    org = org_with_segments
    ceilings = await list_ceilings(db_session, org.id)
    assert len(ceilings) == 1
    assert ceilings[0].ceiling_type == "monthly_cost"


@pytest.mark.asyncio
async def test_list_scale_health(db_session, org_with_segments):
    org = org_with_segments
    await recompute_capacity(db_session, org.id); await db_session.commit()
    health = await list_scale_health(db_session, org.id)
    assert len(health) == 1


@pytest.mark.asyncio
async def test_get_execution_health(db_session, org_with_segments):
    org = org_with_segments
    await recompute_capacity(db_session, org.id); await db_session.commit()
    h = await get_execution_health(db_session, org.id)
    assert "health_status" in h
    assert "recommendation" in h


@pytest.mark.asyncio
async def test_idempotent(db_session, org_with_segments):
    org = org_with_segments
    await recompute_capacity(db_session, org.id); await db_session.commit()
    await recompute_capacity(db_session, org.id); await db_session.commit()
    caps = (await db_session.execute(select(ExecutionCapacityReport).where(ExecutionCapacityReport.organization_id == org.id))).scalars().all()
    assert len(caps) == 1


def test_hyperscale_worker_registered():
    from workers.celery_app import app
    import workers.hyperscale_worker.tasks  # noqa: F401
    assert "workers.hyperscale_worker.tasks.recompute_scale_capacity" in app.tasks
