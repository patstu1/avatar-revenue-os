"""DB-backed integration tests for System Command Center."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.command_center_service import get_command_center_data
from packages.db.enums import ContentType, Platform
from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand, Organization
from packages.db.models.publishing import PerformanceMetric


@pytest_asyncio.fixture
async def brand_with_data(db_session: AsyncSession):
    slug = f"cc-{uuid.uuid4().hex[:6]}"
    org = Organization(name="CC Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="CC Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@cc_{slug}")
    db_session.add(acct)
    await db_session.flush()

    ci = ContentItem(
        brand_id=brand.id,
        creator_account_id=acct.id,
        title="CC Content",
        content_type=ContentType.SHORT_VIDEO,
        platform="tiktok",
        status="published",
    )
    db_session.add(ci)
    await db_session.flush()

    db_session.add(
        PerformanceMetric(
            brand_id=brand.id,
            content_item_id=ci.id,
            creator_account_id=acct.id,
            platform=Platform.TIKTOK,
            impressions=10000,
            clicks=500,
            engagement_rate=0.08,
            revenue=50.0,
        )
    )
    db_session.add(
        AccountStateReport(
            brand_id=brand.id,
            account_id=acct.id,
            current_state="scaling",
            confidence=0.8,
            monetization_intensity="medium",
            posting_cadence="aggressive",
            expansion_eligible=True,
        )
    )
    await db_session.flush()

    return brand


@pytest.mark.asyncio
async def test_command_center_returns_all_sections(db_session, brand_with_data):
    brand = brand_with_data
    data = await get_command_center_data(db_session, brand.id)

    assert "revenue" in data
    assert "providers" in data
    assert "platforms" in data
    assert "accounts" in data
    assert "alerts" in data
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_revenue_section(db_session, brand_with_data):
    brand = brand_with_data
    data = await get_command_center_data(db_session, brand.id)
    rev = data["revenue"]

    assert "lifetime_revenue" in rev
    assert "lifetime_profit" in rev
    assert "today_revenue" in rev
    assert "week_revenue" in rev
    assert "month_revenue" in rev
    assert "by_platform" in rev
    assert "strongest_lane" in rev
    assert "weakest_lane" in rev


@pytest.mark.asyncio
async def test_platform_health(db_session, brand_with_data):
    brand = brand_with_data
    data = await get_command_center_data(db_session, brand.id)
    platforms = data["platforms"]

    assert len(platforms) >= 1
    for p in platforms:
        assert "platform" in p
        assert "status" in p
        assert p["status"] in ("healthy", "weak", "blocked", "saturated", "warming")
        assert "accounts" in p


@pytest.mark.asyncio
async def test_account_ops(db_session, brand_with_data):
    brand = brand_with_data
    data = await get_command_center_data(db_session, brand.id)
    accts = data["accounts"]

    assert accts["total"] >= 1
    assert "scaling" in accts
    assert "weak" in accts
    assert "blocked" in accts
    assert "expansion_eligible" in accts


@pytest.mark.asyncio
async def test_alerts_section(db_session, brand_with_data):
    brand = brand_with_data
    data = await get_command_center_data(db_session, brand.id)
    alerts = data["alerts"]

    assert "critical_alerts" in alerts
    assert "quality_blocks" in alerts
    assert "active_suppressions" in alerts
    assert "top_actions" in alerts
    assert isinstance(alerts["critical_alerts"], list)


@pytest.mark.asyncio
async def test_providers_section(db_session, brand_with_data):
    brand = brand_with_data
    data = await get_command_center_data(db_session, brand.id)
    providers = data["providers"]
    assert isinstance(providers, list)
