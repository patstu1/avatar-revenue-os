"""Integration tests — autonomous content farm: generation pipeline, niche scores, warmup, voice, fleet."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from packages.db.models.core import Organization, Brand
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentBrief, ContentItem, Script
from packages.db.models.autonomous_farm import (
    NicheScore, AccountWarmupPlan, FleetStatusReport, AccountVoiceProfile,
    ContentRepurposeRecord, CompetitorAccount, DailyIntelligenceReport,
)
from packages.db.enums import ContentType, Platform

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def setup_farm(db_session):
    org = Organization(name="Farm Org", slug=f"farm-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(organization_id=org.id, name="Farm Brand", slug=f"fb-{uuid.uuid4().hex[:6]}", niche="personal_finance")
    db_session.add(brand)
    await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.YOUTUBE, platform_username=f"@farm_{uuid.uuid4().hex[:6]}")
    db_session.add(acct)
    await db_session.flush()
    return org, brand, acct


# ── Niche Score Persistence ──

async def test_niche_score_persistence(db_session, setup_farm):
    _, brand, _ = setup_farm
    from packages.scoring.niche_research_engine import score_niche, NICHE_DATABASE
    finance = next(n for n in NICHE_DATABASE if n["niche"] == "personal_finance")
    scored = score_niche(finance, "youtube")

    ns = NicheScore(
        brand_id=brand.id, niche=scored["niche"], platform=scored["platform"],
        composite_score=scored["composite_score"], monetization_score=scored["monetization_score"],
        opportunity_score=scored["opportunity_score"], trend_velocity=scored["trend_velocity"],
        competition=scored["competition"], avg_cpm=scored["avg_cpm"],
        affiliate_density=scored["affiliate_density"], evergreen=scored["evergreen"],
        keywords=scored["keywords"],
    )
    db_session.add(ns)
    await db_session.flush()
    assert ns.id is not None
    assert ns.composite_score > 0


# ── Warmup Plan Persistence ──

async def test_warmup_plan_persistence(db_session, setup_farm):
    _, brand, acct = setup_farm
    from packages.scoring.warmup_engine import determine_warmup_phase
    phase = determine_warmup_phase(datetime.now(timezone.utc) - timedelta(days=10))

    plan = AccountWarmupPlan(
        account_id=acct.id, brand_id=brand.id,
        current_phase=phase["phase"], age_days=phase["age_days"],
        max_posts_per_day=phase["max_posts_per_day"],
        monetization_allowed=phase["monetization_allowed"],
    )
    db_session.add(plan)
    await db_session.flush()
    assert plan.id is not None
    assert plan.current_phase == "trickle"


# ── Voice Profile Persistence ──

async def test_voice_profile_persistence(db_session, setup_farm):
    _, brand, acct = setup_farm
    from packages.scoring.voice_profile_engine import generate_voice_profile
    profile = generate_voice_profile(str(acct.id), "youtube", "personal_finance")

    vp = AccountVoiceProfile(
        account_id=acct.id, brand_id=brand.id,
        style=profile["style"], vocabulary_level=profile["vocabulary_level"],
        emoji_usage=profile["emoji_usage"], preferred_hook_style=profile["preferred_hook_style"],
        cta_style=profile["cta_style"], paragraph_style=profile["paragraph_style"],
        signature_phrases=profile["signature_phrases"], tone_keywords=profile["tone_keywords"],
        avoid_keywords=profile["avoid_keywords"], full_profile=profile,
    )
    db_session.add(vp)
    await db_session.flush()
    assert vp.id is not None
    assert vp.style == profile["style"]


# ── Fleet Status Report ──

async def test_fleet_status_persistence(db_session, setup_farm):
    org, _, _ = setup_farm
    report = FleetStatusReport(
        organization_id=org.id, total_accounts=25,
        accounts_warming=5, accounts_scaling=15,
        accounts_plateaued=3, accounts_suspended=1, accounts_retired=1,
        total_posts_today=42, total_revenue_30d=5000.0,
        expansion_recommended=True,
        expansion_details={"recommended_platform": "tiktok", "recommended_niche": "ai_tools"},
    )
    db_session.add(report)
    await db_session.flush()
    assert report.id is not None
    assert report.expansion_recommended is True


# ── Content Generation Service ──

async def test_generate_content_brief_not_found(db_session, setup_farm):
    from apps.api.services.content_generation_service import generate_content_from_brief
    result = await generate_content_from_brief(db_session, uuid.uuid4())
    assert not result["success"]
    assert "not found" in result["error"]


async def test_generate_content_wrong_status(db_session, setup_farm):
    from apps.api.services.content_generation_service import generate_content_from_brief
    _, brand, acct = setup_farm
    brief = ContentBrief(
        brand_id=brand.id, creator_account_id=acct.id,
        title="Test Brief", content_type=ContentType.SHORT_VIDEO,
        target_platform="youtube", status="script_generated",
    )
    db_session.add(brief)
    await db_session.flush()
    result = await generate_content_from_brief(db_session, brief.id)
    assert not result["success"]
    assert "status" in result["error"]


async def test_generate_content_enriches_metadata(db_session, setup_farm):
    from apps.api.services.content_generation_service import _enrich_brief_metadata
    _, brand, acct = setup_farm
    brief = ContentBrief(
        brand_id=brand.id, creator_account_id=acct.id,
        title="Test Enrichment", content_type=ContentType.SHORT_VIDEO,
        target_platform="youtube", status="draft",
    )
    db_session.add(brief)
    await db_session.flush()
    meta = await _enrich_brief_metadata(db_session, brief)
    assert "winning_patterns" in meta
    assert "losing_patterns" in meta


# ── Competitor Account ──

async def test_competitor_account_persistence(db_session, setup_farm):
    _, brand, _ = setup_farm
    comp = CompetitorAccount(
        brand_id=brand.id, platform="youtube", username="@competitor1",
        niche="personal_finance", follower_count=50000, avg_engagement_rate=0.05,
        posting_frequency=2.0, monetization_methods=["affiliate", "ads"],
        content_gaps=["budgeting tools review", "credit score deep dive"],
    )
    db_session.add(comp)
    await db_session.flush()
    assert comp.id is not None


# ── Daily Intelligence Report ──

async def test_daily_report_persistence(db_session, setup_farm):
    org, _, _ = setup_farm
    report = DailyIntelligenceReport(
        organization_id=org.id, report_date="2026-03-30",
        content_created=42, content_approved=38, content_published=35,
        content_quality_blocked=4, total_impressions=150000,
        total_engagement=12000, total_revenue=450.0,
        top_performing_content=[{"title": "Best budgeting tip", "impressions": 25000}],
        recommendations=[{"action": "Add TikTok account in AI tools niche", "priority": "high"}],
    )
    db_session.add(report)
    await db_session.flush()
    assert report.id is not None
    assert report.total_revenue == 450.0


# ── Content Repurpose Record ──

async def test_repurpose_record_persistence(db_session, setup_farm):
    _, brand, acct = setup_farm
    brief = ContentBrief(brand_id=brand.id, title="Original Long Video", content_type=ContentType.LONG_VIDEO, target_platform="youtube", status="draft")
    db_session.add(brief)
    await db_session.flush()
    ci = ContentItem(brand_id=brand.id, brief_id=brief.id, title="Original Long Video", content_type=ContentType.LONG_VIDEO, platform="youtube", status="approved")
    db_session.add(ci)
    await db_session.flush()
    derived_brief = ContentBrief(brand_id=brand.id, title="Short clip from Original Long Video", content_type=ContentType.SHORT_VIDEO, target_platform="tiktok", status="draft")
    db_session.add(derived_brief)
    await db_session.flush()

    record = ContentRepurposeRecord(
        source_content_id=ci.id, derived_brief_id=derived_brief.id,
        brand_id=brand.id, target_platform="tiktok", target_content_type="SHORT_VIDEO",
    )
    db_session.add(record)
    await db_session.flush()
    assert record.id is not None
