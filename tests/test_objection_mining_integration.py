"""DB-backed integration tests for Objection Mining."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.objection_mining_service import (
    get_objections_for_brief,
    get_priority_report,
    list_clusters,
    list_responses,
    list_signals,
    recompute_objections,
)
from packages.db.enums import ContentType, Platform
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand, Organization
from packages.db.models.learning import CommentIngestion
from packages.db.models.objection_mining import (
    ObjectionCluster,
    ObjectionResponse,
    ObjectionSignal,
)


@pytest_asyncio.fixture
async def brand_with_comments(db_session: AsyncSession):
    slug = f"om-{uuid.uuid4().hex[:6]}"
    org = Organization(name="OM Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="OM Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@om_{slug}")
    db_session.add(acct)
    await db_session.flush()

    ci = ContentItem(brand_id=brand.id, creator_account_id=acct.id, title="Product review", content_type=ContentType.SHORT_VIDEO, platform="tiktok", status="published")
    db_session.add(ci)
    await db_session.flush()

    comments = [
        CommentIngestion(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct.id, platform="tiktok", comment_text="This is way too expensive, can't afford it"),
        CommentIngestion(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct.id, platform="tiktok", comment_text="Is this legit or just a scam? Hard to trust"),
        CommentIngestion(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct.id, platform="tiktok", comment_text="Show me proof it actually works, need evidence"),
        CommentIngestion(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct.id, platform="tiktok", comment_text="Great video, love it!"),
        CommentIngestion(brand_id=brand.id, content_item_id=ci.id, creator_account_id=acct.id, platform="tiktok", comment_text="Too complicated and confusing to understand"),
    ]
    db_session.add_all(comments)
    await db_session.flush()

    return brand, ci


@pytest.mark.asyncio
async def test_recompute_extracts_signals(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    result = await recompute_objections(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"
    assert result["rows_processed"] >= 3

    signals = (await db_session.execute(
        select(ObjectionSignal).where(ObjectionSignal.brand_id == brand.id)
    )).scalars().all()
    assert len(signals) >= 3
    types = {s.objection_type for s in signals}
    assert "price" in types
    assert "trust" in types


@pytest.mark.asyncio
async def test_clusters_created(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    await recompute_objections(db_session, brand.id)
    await db_session.commit()

    clusters = (await db_session.execute(
        select(ObjectionCluster).where(ObjectionCluster.brand_id == brand.id)
    )).scalars().all()
    assert len(clusters) >= 2
    for c in clusters:
        assert c.signal_count >= 1
        assert c.recommended_response_angle


@pytest.mark.asyncio
async def test_responses_created(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    await recompute_objections(db_session, brand.id)
    await db_session.commit()

    responses = (await db_session.execute(
        select(ObjectionResponse).where(ObjectionResponse.brand_id == brand.id)
    )).scalars().all()
    assert len(responses) >= 3
    channels = {r.target_channel for r in responses}
    assert "content_brief" in channels


@pytest.mark.asyncio
async def test_priority_report_created(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    await recompute_objections(db_session, brand.id)
    await db_session.commit()

    report = await get_priority_report(db_session, brand.id)
    assert report is not None
    assert report.total_signals >= 3
    assert report.highest_impact_type is not None


@pytest.mark.asyncio
async def test_list_signals(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    await recompute_objections(db_session, brand.id)
    await db_session.commit()
    sigs = await list_signals(db_session, brand.id)
    assert len(sigs) >= 3


@pytest.mark.asyncio
async def test_list_clusters(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    await recompute_objections(db_session, brand.id)
    await db_session.commit()
    cl = await list_clusters(db_session, brand.id)
    assert len(cl) >= 2


@pytest.mark.asyncio
async def test_list_responses(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    await recompute_objections(db_session, brand.id)
    await db_session.commit()
    resp = await list_responses(db_session, brand.id)
    assert len(resp) >= 3


@pytest.mark.asyncio
async def test_get_objections_for_brief(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    await recompute_objections(db_session, brand.id)
    await db_session.commit()
    brief_data = await get_objections_for_brief(db_session, brand.id)
    assert isinstance(brief_data, list)
    assert len(brief_data) >= 2
    for item in brief_data:
        assert "type" in item
        assert "impact" in item
        assert "angle" in item


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_comments):
    brand, _ = brand_with_comments
    r1 = await recompute_objections(db_session, brand.id)
    await db_session.commit()
    r2 = await recompute_objections(db_session, brand.id)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]


def test_objection_mining_worker_registered():
    import workers.objection_mining_worker.tasks  # noqa: F401
    from workers.celery_app import app
    assert "workers.objection_mining_worker.tasks.recompute_objection_mining" in app.tasks
