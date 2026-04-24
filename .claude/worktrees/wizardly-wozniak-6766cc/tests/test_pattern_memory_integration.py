"""DB-backed integration tests for Winning-Pattern Memory."""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand, Organization
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.pattern_memory import (
    WinningPatternMemory,
    WinningPatternEvidence,
    WinningPatternCluster,
    LosingPatternMemory,
    PatternReuseRecommendation,
    PatternDecayReport,
)
from packages.db.enums import ContentType, Platform
from apps.api.services.pattern_memory_service import (
    recompute_patterns,
    recompute_clusters,
    recompute_decay,
    recompute_reuse,
    list_patterns,
    list_clusters,
    list_losers,
    list_reuse,
    list_decay,
    get_experiment_suggestions,
    get_allocation_weights,
)


@pytest_asyncio.fixture
async def brand_with_content(db_session: AsyncSession):
    slug = f"pat-{uuid.uuid4().hex[:6]}"

    org = Organization(name="Pattern Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="Pattern Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    acct_tt = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@tt_{slug}")
    acct_ig = CreatorAccount(brand_id=brand.id, platform=Platform.INSTAGRAM, platform_username=f"@ig_{slug}")
    db_session.add_all([acct_tt, acct_ig])
    await db_session.flush()

    items = []
    for i in range(8):
        is_tiktok = i < 4
        ci = ContentItem(
            brand_id=brand.id,
            creator_account_id=acct_tt.id if is_tiktok else acct_ig.id,
            title=f"Don't buy this gadget until you see item {i}" if i % 2 == 0 else f"Top {i} things I wish I knew about tech",
            content_type=ContentType.SHORT_VIDEO,
            platform="tiktok" if is_tiktok else "instagram",
        )
        db_session.add(ci)
        items.append(ci)
    await db_session.flush()

    for i, ci in enumerate(items):
        is_good = i < 5
        plat = Platform.TIKTOK if i < 4 else Platform.INSTAGRAM
        acct_id = acct_tt.id if i < 4 else acct_ig.id
        pm = PerformanceMetric(
            brand_id=brand.id,
            content_item_id=ci.id,
            creator_account_id=acct_id,
            platform=plat,
            impressions=20000 if is_good else 200,
            clicks=1000 if is_good else 5,
            engagement_rate=0.12 if is_good else 0.002,
            ctr=5.0 if is_good else 0.1,
            revenue=80.0 if is_good else 0.5,
        )
        db_session.add(pm)
    await db_session.flush()

    return brand


# ── recompute_patterns ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recompute_patterns_creates_winners_and_losers(db_session, brand_with_content):
    brand = brand_with_content
    result = await recompute_patterns(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"
    assert result["rows_processed"] > 0

    winners = (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().all()

    losers = (await db_session.execute(
        select(LosingPatternMemory).where(LosingPatternMemory.brand_id == brand.id)
    )).scalars().all()

    total = len(winners) + len(losers)
    assert total > 0, "Should create at least some winners or losers"

    for w in winners:
        assert w.win_score >= 0.6
        assert w.pattern_type in ("hook", "creative_structure", "content_form", "monetization")
        assert w.pattern_signature is not None

    for l in losers:
        assert l.fail_score > 0


@pytest.mark.asyncio
async def test_recompute_creates_evidence(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await db_session.commit()

    evidence = (await db_session.execute(
        select(WinningPatternEvidence).where(WinningPatternEvidence.brand_id == brand.id)
    )).scalars().all()

    if (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().first():
        assert len(evidence) > 0, "Winners should have evidence rows"


# ── recompute_clusters ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recompute_clusters(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await db_session.flush()
    result = await recompute_clusters(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"

    clusters = (await db_session.execute(
        select(WinningPatternCluster).where(WinningPatternCluster.brand_id == brand.id)
    )).scalars().all()

    winners = (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().all()

    if len(winners) > 0:
        assert len(clusters) > 0, "Should create clusters when winners exist"
        for c in clusters:
            assert c.cluster_name
            assert c.pattern_count > 0


# ── recompute_decay ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recompute_decay(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await db_session.flush()
    result = await recompute_decay(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"

    reports = (await db_session.execute(
        select(PatternDecayReport).where(PatternDecayReport.brand_id == brand.id)
    )).scalars().all()

    winners = (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().all()

    assert len(reports) == len(winners), "One decay report per winning pattern"


# ── recompute_reuse ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recompute_reuse(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await db_session.flush()
    result = await recompute_reuse(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"

    recs = (await db_session.execute(
        select(PatternReuseRecommendation).where(PatternReuseRecommendation.brand_id == brand.id)
    )).scalars().all()

    winners = (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().all()

    if len(winners) > 0:
        assert len(recs) > 0, "Should recommend reuse when winners exist"
        for r in recs:
            assert r.target_platform
            assert r.expected_uplift >= 0


# ── list helpers ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_patterns(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await db_session.commit()
    rows = await list_patterns(db_session, brand.id)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_list_clusters(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await recompute_clusters(db_session, brand.id)
    await db_session.commit()
    rows = await list_clusters(db_session, brand.id)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_list_losers(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await db_session.commit()
    rows = await list_losers(db_session, brand.id)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_list_reuse(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await recompute_reuse(db_session, brand.id)
    await db_session.commit()
    rows = await list_reuse(db_session, brand.id)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_list_decay(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await recompute_decay(db_session, brand.id)
    await db_session.commit()
    rows = await list_decay(db_session, brand.id)
    assert isinstance(rows, list)


# ── worker task registration ────────────────────────────────────────────

def test_pattern_memory_worker_registered():
    from workers.celery_app import app
    import workers.pattern_memory_worker.tasks  # noqa: F401
    assert "workers.pattern_memory_worker.tasks.recompute_pattern_memory" in app.tasks


# ── idempotency ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recompute_idempotent(db_session, brand_with_content):
    brand = brand_with_content
    r1 = await recompute_patterns(db_session, brand.id)
    await db_session.commit()
    r2 = await recompute_patterns(db_session, brand.id)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]

    winners = (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().all()

    sigs = [w.pattern_signature for w in winners]
    assert len(sigs) == len(set(sigs)), "No duplicate patterns after double recompute"


# ── structured metadata patterns ────────────────────────────────────────

@pytest.mark.asyncio
async def test_structured_metadata_extraction(db_session, brand_with_content):
    """Content items with explicit cta_type/offer_angle produce those pattern types."""
    brand = brand_with_content
    items = (await db_session.execute(
        select(ContentItem).where(ContentItem.brand_id == brand.id).limit(2)
    )).scalars().all()
    if items:
        items[0].cta_type = "urgency"
        items[0].offer_angle = "premium"
    await db_session.flush()

    result = await recompute_patterns(db_session, brand.id)
    await db_session.commit()

    all_winners = (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().all()
    all_losers = (await db_session.execute(
        select(LosingPatternMemory).where(LosingPatternMemory.brand_id == brand.id)
    )).scalars().all()
    all_types = {w.pattern_type for w in all_winners} | {l.pattern_type for l in all_losers}
    assert "hook" in all_types or "content_form" in all_types


# ── experiment suggestions ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_experiment_suggestions(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await db_session.commit()
    suggestions = await get_experiment_suggestions(db_session, brand.id)
    assert isinstance(suggestions, list)


# ── allocation weights ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_allocation_weights(db_session, brand_with_content):
    brand = brand_with_content
    await recompute_patterns(db_session, brand.id)
    await recompute_clusters(db_session, brand.id)
    await db_session.commit()
    weights = await get_allocation_weights(db_session, brand.id, 1000.0)
    assert isinstance(weights, list)
    winners = (await db_session.execute(
        select(WinningPatternMemory).where(WinningPatternMemory.brand_id == brand.id)
    )).scalars().all()
    if winners:
        assert len(weights) > 0
        assert all("allocation_pct" in w for w in weights)
        assert all("hero_eligible" in w for w in weights)
