"""DB-backed integration tests for Brand Governance OS."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.brand_governance_service import (
    evaluate_content,
    get_governance_for_content,
    list_profiles,
    list_violations,
    list_voice_rules,
    recompute_governance,
)
from packages.db.enums import ContentType, Platform
from packages.db.models.accounts import CreatorAccount
from packages.db.models.brand_governance import (
    BrandAssetLibrary,
    BrandAudienceProfile,
    BrandGovernanceProfile,
    BrandGovernanceViolation,
    BrandKnowledgeBase,
    BrandVoiceRule,
)
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand, Organization


@pytest_asyncio.fixture
async def brand_with_governance(db_session: AsyncSession):
    slug = f"bg-{uuid.uuid4().hex[:6]}"
    org = Organization(name="BG Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    brand = Brand(organization_id=org.id, name="BG Brand", slug=slug, niche="tech")
    db_session.add(brand); await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@bg_{slug}")
    db_session.add(acct); await db_session.flush()

    db_session.add(BrandGovernanceProfile(brand_id=brand.id, tone_profile="professional, data-driven, transparent", governance_level="strict"))
    db_session.add(BrandVoiceRule(brand_id=brand.id, rule_type="banned_phrase", rule_key="guaranteed results", severity="hard"))
    db_session.add(BrandVoiceRule(brand_id=brand.id, rule_type="required_phrase", rule_key="affiliate disclosure", severity="soft"))
    db_session.add(BrandKnowledgeBase(brand_id=brand.id, kb_type="product", title="Product Knowledge"))
    db_session.add(BrandAudienceProfile(brand_id=brand.id, segment_name="Tech enthusiasts", trust_level="medium"))
    db_session.add(BrandAssetLibrary(brand_id=brand.id, asset_type="logo", asset_name="Brand Logo"))
    await db_session.flush()

    good_ci = ContentItem(brand_id=brand.id, creator_account_id=acct.id, title="Professional data-driven review with affiliate disclosure", description="Transparent analysis of the product. Affiliate disclosure included.", content_type=ContentType.SHORT_VIDEO, platform="tiktok", status="draft")
    bad_ci = ContentItem(brand_id=brand.id, creator_account_id=acct.id, title="Get guaranteed results NOW!", description="This product gives guaranteed results fast.", content_type=ContentType.SHORT_VIDEO, platform="tiktok", status="draft")
    db_session.add_all([good_ci, bad_ci]); await db_session.flush()
    return brand, good_ci, bad_ci


@pytest.mark.asyncio
async def test_evaluate_good_content(db_session, brand_with_governance):
    brand, good_ci, _ = brand_with_governance
    result = await evaluate_content(db_session, brand.id, good_ci.id)
    await db_session.commit()
    assert result["violations"] == 0

@pytest.mark.asyncio
async def test_evaluate_bad_content(db_session, brand_with_governance):
    brand, _, bad_ci = brand_with_governance
    result = await evaluate_content(db_session, brand.id, bad_ci.id)
    await db_session.commit()
    assert result["violations"] >= 1
    viols = (await db_session.execute(select(BrandGovernanceViolation).where(BrandGovernanceViolation.content_item_id == bad_ci.id))).scalars().all()
    assert any(v.violation_type == "banned_phrase" for v in viols)

@pytest.mark.asyncio
async def test_recompute_governance(db_session, brand_with_governance):
    brand, _, _ = brand_with_governance
    result = await recompute_governance(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] == 2

@pytest.mark.asyncio
async def test_list_profiles(db_session, brand_with_governance):
    brand, _, _ = brand_with_governance
    profiles = await list_profiles(db_session, brand.id)
    assert len(profiles) == 1
    assert profiles[0].governance_level == "strict"

@pytest.mark.asyncio
async def test_list_voice_rules(db_session, brand_with_governance):
    brand, _, _ = brand_with_governance
    rules = await list_voice_rules(db_session, brand.id)
    assert len(rules) == 2

@pytest.mark.asyncio
async def test_list_violations(db_session, brand_with_governance):
    brand, _, bad_ci = brand_with_governance
    await evaluate_content(db_session, brand.id, bad_ci.id); await db_session.commit()
    viols = await list_violations(db_session, brand.id)
    assert len(viols) >= 1

@pytest.mark.asyncio
async def test_get_governance_for_content(db_session, brand_with_governance):
    brand, _, _ = brand_with_governance
    gov = await get_governance_for_content(db_session, brand.id)
    assert "banned_phrases" in gov
    assert "guaranteed results" in gov["banned_phrases"]
    assert gov["governance_level"] == "strict"

@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_governance):
    brand, _, _ = brand_with_governance
    r1 = await recompute_governance(db_session, brand.id); await db_session.commit()
    r2 = await recompute_governance(db_session, brand.id); await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]

def test_brand_governance_worker_registered():
    import workers.brand_governance_worker.tasks  # noqa: F401
    from workers.celery_app import app
    assert "workers.brand_governance_worker.tasks.recompute_brand_governance" in app.tasks
