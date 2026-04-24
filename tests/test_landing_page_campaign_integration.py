"""DB-backed integration tests for Landing Pages + Campaigns."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.campaign_service import (
    get_campaign_for_content,
    list_campaign_blockers,
    list_campaign_variants,
    list_campaigns,
    recompute_campaigns,
)
from apps.api.services.landing_page_service import (
    get_best_page_for_offer,
    list_pages,
    list_quality,
    list_variants,
    recompute_landing_pages,
)
from packages.db.enums import Platform
from packages.db.models.accounts import CreatorAccount
from packages.db.models.campaigns import Campaign, CampaignBlocker, CampaignVariant
from packages.db.models.core import Brand, Organization
from packages.db.models.landing_pages import LandingPage, LandingPageQualityReport, LandingPageVariant
from packages.db.models.offers import Offer


@pytest_asyncio.fixture
async def brand_with_offer(db_session: AsyncSession):
    slug = f"lpc-{uuid.uuid4().hex[:6]}"
    org = Organization(name="LPC Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(organization_id=org.id, name="LPC Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@lpc_{slug}")
    db_session.add(acct)
    await db_session.flush()
    offer = Offer(
        brand_id=brand.id,
        name="LPC Offer",
        monetization_method="affiliate",
        payout_amount=30.0,
        epc=2.5,
        conversion_rate=0.05,
    )
    db_session.add(offer)
    await db_session.flush()
    return brand, offer, acct


@pytest.mark.asyncio
async def test_recompute_landing_pages(db_session, brand_with_offer):
    brand, offer, _ = brand_with_offer
    result = await recompute_landing_pages(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 3
    pages = (await db_session.execute(select(LandingPage).where(LandingPage.brand_id == brand.id))).scalars().all()
    assert len(pages) >= 3
    types = {p.page_type for p in pages}
    assert "product" in types and "review" in types


@pytest.mark.asyncio
async def test_variants_created(db_session, brand_with_offer):
    brand, _, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.commit()
    variants = (
        (await db_session.execute(select(LandingPageVariant).join(LandingPage).where(LandingPage.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(variants) >= 6


@pytest.mark.asyncio
async def test_quality_scored(db_session, brand_with_offer):
    brand, _, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.commit()
    quality = (
        (
            await db_session.execute(
                select(LandingPageQualityReport).where(LandingPageQualityReport.brand_id == brand.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(quality) >= 3
    for q in quality:
        assert q.verdict in ("pass", "warn", "fail")


@pytest.mark.asyncio
async def test_get_best_page(db_session, brand_with_offer):
    brand, offer, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.commit()
    best = await get_best_page_for_offer(db_session, brand.id, offer.id)
    assert best["page_id"] is not None
    assert best["truth_label"] == "recommendation_only"


@pytest.mark.asyncio
async def test_recompute_campaigns(db_session, brand_with_offer):
    brand, offer, acct = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.flush()
    result = await recompute_campaigns(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 2


@pytest.mark.asyncio
async def test_campaign_linked_to_page(db_session, brand_with_offer):
    brand, offer, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.flush()
    await recompute_campaigns(db_session, brand.id)
    await db_session.commit()
    camps = (await db_session.execute(select(Campaign).where(Campaign.brand_id == brand.id))).scalars().all()
    linked = [c for c in camps if c.landing_page_id is not None]
    assert len(linked) >= 1


@pytest.mark.asyncio
async def test_campaign_blockers(db_session, brand_with_offer):
    brand, _, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.flush()
    await recompute_campaigns(db_session, brand.id)
    await db_session.commit()
    blockers = (
        (await db_session.execute(select(CampaignBlocker).where(CampaignBlocker.brand_id == brand.id))).scalars().all()
    )
    assert isinstance(blockers, list)


@pytest.mark.asyncio
async def test_campaign_variants(db_session, brand_with_offer):
    brand, _, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.flush()
    await recompute_campaigns(db_session, brand.id)
    await db_session.commit()
    variants = (
        (await db_session.execute(select(CampaignVariant).join(Campaign).where(Campaign.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(variants) >= 4


@pytest.mark.asyncio
async def test_get_campaign_for_content(db_session, brand_with_offer):
    brand, offer, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.flush()
    await recompute_campaigns(db_session, brand.id)
    await db_session.commit()
    camp = await get_campaign_for_content(db_session, brand.id, offer.id)
    assert camp["campaign_id"] is not None
    assert camp["truth_label"] == "recommendation_only"


@pytest.mark.asyncio
async def test_truth_labels_honest(db_session, brand_with_offer):
    brand, _, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.flush()
    await recompute_campaigns(db_session, brand.id)
    await db_session.commit()
    pages = (await db_session.execute(select(LandingPage).where(LandingPage.brand_id == brand.id))).scalars().all()
    for p in pages:
        assert p.truth_label == "recommendation_only"
        assert p.publish_status == "unpublished"
    camps = (await db_session.execute(select(Campaign).where(Campaign.brand_id == brand.id))).scalars().all()
    for c in camps:
        assert c.truth_label == "recommendation_only"


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_offer):
    brand, _, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.commit()
    r1 = await recompute_landing_pages(db_session, brand.id)
    await db_session.commit()
    r2 = await recompute_landing_pages(db_session, brand.id)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]


@pytest.mark.asyncio
async def test_list_helpers(db_session, brand_with_offer):
    brand, _, _ = brand_with_offer
    await recompute_landing_pages(db_session, brand.id)
    await db_session.flush()
    await recompute_campaigns(db_session, brand.id)
    await db_session.commit()
    assert len(await list_pages(db_session, brand.id)) >= 3
    assert len(await list_variants(db_session, brand.id)) >= 6
    assert len(await list_quality(db_session, brand.id)) >= 3
    assert len(await list_campaigns(db_session, brand.id)) >= 2
    assert len(await list_campaign_variants(db_session, brand.id)) >= 4
    assert isinstance(await list_campaign_blockers(db_session, brand.id), list)


def test_lp_worker_registered():
    import workers.campaign_worker.tasks
    import workers.landing_page_worker.tasks  # noqa: F401, E702
    from workers.celery_app import app

    assert "workers.landing_page_worker.tasks.recompute_landing_pages" in app.tasks
    assert "workers.campaign_worker.tasks.recompute_campaigns" in app.tasks
