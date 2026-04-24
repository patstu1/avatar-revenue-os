"""DB-backed integration tests for Recovery Engine."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.recovery_engine_service import (
    get_recovery_summary,
    list_incidents,
    recompute_recovery,
)
from packages.db.models.core import Organization
from packages.db.models.provider_registry import ProviderBlocker
from packages.db.models.recovery_engine import RecoveryIncidentV2, RerouteAction, ThrottlingAction


@pytest_asyncio.fixture
async def org_with_failures(db_session: AsyncSession):
    slug = f"rec-{uuid.uuid4().hex[:6]}"
    org = Organization(name="REC Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    from packages.db.models.core import Brand

    brand = Brand(organization_id=org.id, name="REC Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    db_session.add(
        ProviderBlocker(
            brand_id=brand.id,
            provider_key="stripe",
            blocker_type="api_failure",
            severity="critical",
            description="Stripe API returning 500 errors",
            operator_action_needed="Check Stripe dashboard",
        )
    )
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_recompute_detects_incidents(db_session, org_with_failures):
    org = org_with_failures
    result = await recompute_recovery(db_session, org.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 1


@pytest.mark.asyncio
async def test_incidents_created(db_session, org_with_failures):
    org = org_with_failures
    await recompute_recovery(db_session, org.id)
    await db_session.commit()
    incidents = (
        (await db_session.execute(select(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org.id)))
        .scalars()
        .all()
    )
    assert len(incidents) >= 1
    assert incidents[0].incident_type == "provider_failure"
    assert incidents[0].recovery_status in ("auto_recovering", "escalated")


@pytest.mark.asyncio
async def test_reroute_actions_created(db_session, org_with_failures):
    org = org_with_failures
    await recompute_recovery(db_session, org.id)
    await db_session.commit()
    reroutes = (
        (
            await db_session.execute(
                select(RerouteAction).join(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(reroutes) >= 1


@pytest.mark.asyncio
async def test_throttle_actions_created(db_session, org_with_failures):
    org = org_with_failures
    await recompute_recovery(db_session, org.id)
    await db_session.commit()
    throttles = (
        (
            await db_session.execute(
                select(ThrottlingAction).join(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(throttles) >= 1


@pytest.mark.asyncio
async def test_list_incidents(db_session, org_with_failures):
    org = org_with_failures
    await recompute_recovery(db_session, org.id)
    await db_session.commit()
    incidents = await list_incidents(db_session, org.id)
    assert len(incidents) >= 1


@pytest.mark.asyncio
async def test_get_recovery_summary(db_session, org_with_failures):
    org = org_with_failures
    await recompute_recovery(db_session, org.id)
    await db_session.commit()
    s = await get_recovery_summary(db_session, org.id)
    assert s["open_incidents"] >= 1


@pytest.mark.asyncio
async def test_idempotent(db_session, org_with_failures):
    org = org_with_failures
    await recompute_recovery(db_session, org.id)
    await db_session.commit()
    await recompute_recovery(db_session, org.id)
    await db_session.commit()
    incidents = (
        (await db_session.execute(select(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org.id)))
        .scalars()
        .all()
    )
    assert len(incidents) >= 1


def test_recovery_worker_registered():
    import workers.recovery_engine_worker.tasks  # noqa: F401
    from workers.celery_app import app

    assert "workers.recovery_engine_worker.tasks.scan_recovery" in app.tasks
