"""DB-backed integration tests for Quality Governor."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.quality_governor_service import (
    get_publish_eligibility,
    list_blocks,
    list_reports,
    recompute_brand_quality,
    score_content_item,
)
from packages.db.enums import ContentType, Platform
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand, Organization
from packages.db.models.quality_governor import (
    QualityDimensionScore,
    QualityGovernorReport,
    QualityImprovementAction,
)


@pytest_asyncio.fixture
async def brand_with_content(db_session: AsyncSession):
    slug = f"qg-{uuid.uuid4().hex[:6]}"
    org = Organization(name="QG Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="QG Brand", slug=slug, niche="tech", tone_of_voice="professional")
    db_session.add(brand)
    await db_session.flush()

    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@qg_{slug}")
    db_session.add(acct)
    await db_session.flush()

    good_ci = ContentItem(
        brand_id=brand.id, creator_account_id=acct.id,
        title="Why you should never ignore this secret productivity hack?",
        description="This is a detailed guide about improving productivity. " * 15,
        content_type=ContentType.SHORT_VIDEO, platform="tiktok",
        cta_type="direct", monetization_method="affiliate", status="draft",
    )
    bad_ci = ContentItem(
        brand_id=brand.id, creator_account_id=acct.id,
        title="x", description="",
        content_type=ContentType.TEXT_POST, platform="tiktok",
        status="draft",
    )
    db_session.add_all([good_ci, bad_ci])
    await db_session.flush()

    return brand, acct, good_ci, bad_ci


@pytest.mark.asyncio
async def test_score_good_content(db_session, brand_with_content):
    brand, _, good_ci, _ = brand_with_content
    result = await score_content_item(db_session, brand.id, good_ci.id)
    await db_session.commit()

    assert result["verdict"] == "pass"
    assert result["publish_allowed"] is True
    assert result["total_score"] >= 0.5

    report = (await db_session.execute(
        select(QualityGovernorReport).where(QualityGovernorReport.content_item_id == good_ci.id)
    )).scalar_one_or_none()
    assert report is not None
    assert report.verdict == "pass"


@pytest.mark.asyncio
async def test_score_bad_content(db_session, brand_with_content):
    brand, _, _, bad_ci = brand_with_content
    result = await score_content_item(db_session, brand.id, bad_ci.id)
    await db_session.commit()

    assert result["verdict"] in ("fail", "warn")


@pytest.mark.asyncio
async def test_dimension_scores_created(db_session, brand_with_content):
    brand, _, good_ci, _ = brand_with_content
    await score_content_item(db_session, brand.id, good_ci.id)
    await db_session.commit()

    report = (await db_session.execute(
        select(QualityGovernorReport).where(QualityGovernorReport.content_item_id == good_ci.id)
    )).scalar_one()
    dims = (await db_session.execute(
        select(QualityDimensionScore).where(QualityDimensionScore.report_id == report.id)
    )).scalars().all()
    assert len(dims) == 10
    dim_names = {d.dimension for d in dims}
    for expected in ("hook_strength", "clarity", "trust_risk", "duplication_risk"):
        assert expected in dim_names


@pytest.mark.asyncio
async def test_improvements_created(db_session, brand_with_content):
    brand, _, _, bad_ci = brand_with_content
    await score_content_item(db_session, brand.id, bad_ci.id)
    await db_session.commit()

    report = (await db_session.execute(
        select(QualityGovernorReport).where(QualityGovernorReport.content_item_id == bad_ci.id)
    )).scalar_one()
    imps = (await db_session.execute(
        select(QualityImprovementAction).where(QualityImprovementAction.report_id == report.id)
    )).scalars().all()
    assert len(imps) >= 1


@pytest.mark.asyncio
async def test_recompute_brand_quality(db_session, brand_with_content):
    brand, _, _, _ = brand_with_content
    result = await recompute_brand_quality(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] == 2


@pytest.mark.asyncio
async def test_list_reports(db_session, brand_with_content):
    brand, _, _, _ = brand_with_content
    await recompute_brand_quality(db_session, brand.id)
    await db_session.commit()
    reports = await list_reports(db_session, brand.id)
    assert len(reports) == 2


@pytest.mark.asyncio
async def test_list_blocks(db_session, brand_with_content):
    brand, _, _, _ = brand_with_content
    await recompute_brand_quality(db_session, brand.id)
    await db_session.commit()
    blocks = await list_blocks(db_session, brand.id)
    assert isinstance(blocks, list)


@pytest.mark.asyncio
async def test_get_publish_eligibility(db_session, brand_with_content):
    brand, _, good_ci, _ = brand_with_content
    await score_content_item(db_session, brand.id, good_ci.id)
    await db_session.commit()
    elig = await get_publish_eligibility(db_session, good_ci.id)
    assert elig["publish_allowed"] is True
    assert elig["verdict"] == "pass"


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_content):
    brand, _, good_ci, _ = brand_with_content
    await score_content_item(db_session, brand.id, good_ci.id)
    await db_session.commit()
    await score_content_item(db_session, brand.id, good_ci.id)
    await db_session.commit()

    reports = (await db_session.execute(
        select(QualityGovernorReport).where(QualityGovernorReport.content_item_id == good_ci.id)
    )).scalars().all()
    assert len(reports) == 1


def test_quality_governor_worker_registered():
    import workers.quality_governor_worker.tasks  # noqa: F401
    from workers.celery_app import app
    assert "workers.quality_governor_worker.tasks.recompute_quality_governor" in app.tasks
