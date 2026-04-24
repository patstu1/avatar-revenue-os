"""DB-backed integration tests for Creator Revenue Avenues Phase A."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand, Organization
from packages.db.models.creator_revenue import (
    CreatorRevenueBlocker,
    CreatorRevenueEvent,
    CreatorRevenueOpportunity,
    PremiumAccessAction,
    ServiceConsultingAction,
    UgcServiceAction,
)

BRAND_ID = uuid.UUID("00000000-0000-0000-0000-000000000200")


@pytest_asyncio.fixture
async def seed_brand(db_session: AsyncSession):
    org = Organization(name="CRA Test Org", slug="cra-test-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(id=BRAND_ID, name="CRA Test Brand", slug="cra-test-brand", organization_id=org.id)
    db_session.add(brand)
    await db_session.commit()
    return brand


@pytest.mark.asyncio
async def test_recompute_opportunities_creates_records(db_session: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_opportunities

    result = await recompute_opportunities(db_session, BRAND_ID)
    assert result["created"] > 0

    opps = list(
        (
            await db_session.execute(
                select(CreatorRevenueOpportunity).where(
                    CreatorRevenueOpportunity.brand_id == BRAND_ID,
                    CreatorRevenueOpportunity.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(opps) >= 1
    assert all(o.confidence > 0 for o in opps)


@pytest.mark.asyncio
async def test_recompute_ugc_services_creates_records(db_session: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_ugc_services

    result = await recompute_ugc_services(db_session, BRAND_ID)
    assert result["created"] > 0

    actions = list(
        (
            await db_session.execute(
                select(UgcServiceAction).where(
                    UgcServiceAction.brand_id == BRAND_ID,
                    UgcServiceAction.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) >= 1
    for a in actions:
        assert a.service_type is not None
        assert a.expected_value >= 0


@pytest.mark.asyncio
async def test_recompute_service_consulting_creates_records(db_session: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_service_consulting

    result = await recompute_service_consulting(db_session, BRAND_ID)
    assert result["created"] > 0

    actions = list(
        (
            await db_session.execute(
                select(ServiceConsultingAction).where(
                    ServiceConsultingAction.brand_id == BRAND_ID,
                    ServiceConsultingAction.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) >= 1
    for a in actions:
        assert a.service_type is not None
        assert a.expected_deal_value >= 0


@pytest.mark.asyncio
async def test_recompute_premium_access_creates_records(db_session: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_premium_access

    result = await recompute_premium_access(db_session, BRAND_ID)
    assert result["created"] > 0

    actions = list(
        (
            await db_session.execute(
                select(PremiumAccessAction).where(
                    PremiumAccessAction.brand_id == BRAND_ID,
                    PremiumAccessAction.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) >= 1
    for a in actions:
        assert a.offer_type is not None
        assert a.revenue_model in ("recurring", "one_time")


@pytest.mark.asyncio
async def test_recompute_blockers_detects_issues(db_session: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_blockers

    result = await recompute_blockers(db_session, BRAND_ID)
    assert result["created"] > 0

    blockers = list(
        (
            await db_session.execute(
                select(CreatorRevenueBlocker).where(
                    CreatorRevenueBlocker.brand_id == BRAND_ID,
                    CreatorRevenueBlocker.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(blockers) >= 1
    for b in blockers:
        assert b.blocker_type is not None
        assert b.operator_action_needed is not None


@pytest.mark.asyncio
async def test_revenue_event_persistence(db_session: AsyncSession, seed_brand):
    event = CreatorRevenueEvent(
        brand_id=BRAND_ID,
        avenue_type="ugc_services",
        event_type="deal_closed",
        revenue=1500.0,
        cost=200.0,
        profit=1300.0,
        client_name="Test Client",
        description="UGC package sold",
    )
    db_session.add(event)
    await db_session.commit()

    events = list(
        (await db_session.execute(select(CreatorRevenueEvent).where(CreatorRevenueEvent.brand_id == BRAND_ID)))
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].profit == 1300.0
    assert events[0].client_name == "Test Client"


@pytest.mark.asyncio
async def test_idempotent_recompute_replaces_old(db_session: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_opportunities

    await recompute_opportunities(db_session, BRAND_ID)
    first_opps = list(
        (
            await db_session.execute(
                select(CreatorRevenueOpportunity).where(
                    CreatorRevenueOpportunity.brand_id == BRAND_ID,
                    CreatorRevenueOpportunity.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    first_count = len(first_opps)

    await recompute_opportunities(db_session, BRAND_ID)
    second_opps = list(
        (
            await db_session.execute(
                select(CreatorRevenueOpportunity).where(
                    CreatorRevenueOpportunity.brand_id == BRAND_ID,
                    CreatorRevenueOpportunity.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(second_opps) == first_count

    all_opps = list(
        (
            await db_session.execute(
                select(CreatorRevenueOpportunity).where(
                    CreatorRevenueOpportunity.brand_id == BRAND_ID,
                )
            )
        )
        .scalars()
        .all()
    )
    inactive = [o for o in all_opps if not o.is_active]
    assert len(inactive) >= first_count


@pytest.mark.asyncio
async def test_opportunity_links_to_ugc_action(db_session: AsyncSession, seed_brand):
    from apps.api.services.creator_revenue_service import recompute_opportunities, recompute_ugc_services

    await recompute_opportunities(db_session, BRAND_ID)
    await recompute_ugc_services(db_session, BRAND_ID)

    opps = list(
        (
            await db_session.execute(
                select(CreatorRevenueOpportunity).where(
                    CreatorRevenueOpportunity.brand_id == BRAND_ID,
                    CreatorRevenueOpportunity.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    ugc = list(
        (
            await db_session.execute(
                select(UgcServiceAction).where(
                    UgcServiceAction.brand_id == BRAND_ID,
                    UgcServiceAction.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(opps) >= 1
    assert len(ugc) >= 1
