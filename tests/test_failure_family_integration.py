"""DB-backed integration tests for Failure-Family Suppression."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.failure_family_service import (
    get_active_suppressions_for_downstream,
    list_reports,
    list_suppression_rules,
    recompute_failure_families,
    run_decay_check,
)
from packages.db.models.core import Brand, Organization
from packages.db.models.failure_family import (
    FailureFamilyMember,
    FailureFamilyReport,
    SuppressionRule,
)
from packages.db.models.pattern_memory import LosingPatternMemory
from packages.scoring.pattern_memory_engine import _sig


@pytest_asyncio.fixture
async def brand_with_losers(db_session: AsyncSession):
    slug = f"ff-{uuid.uuid4().hex[:6]}"
    org = Organization(name="FF Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()

    brand = Brand(organization_id=org.id, name="FF Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()

    for i in range(5):
        db_session.add(LosingPatternMemory(
            brand_id=brand.id, pattern_type="hook", pattern_name="curiosity",
            pattern_signature=_sig("hook", f"curiosity_{i}"), fail_score=0.8,
            suppress_reason="test", evidence_json={},
        ))
    for i in range(2):
        db_session.add(LosingPatternMemory(
            brand_id=brand.id, pattern_type="content_form", pattern_name="carousel",
            pattern_signature=_sig("content_form", f"carousel_{i}"), fail_score=0.7,
            suppress_reason="test", evidence_json={},
        ))
    await db_session.flush()
    return brand


@pytest.mark.asyncio
async def test_recompute_creates_families(db_session, brand_with_losers):
    brand = brand_with_losers
    result = await recompute_failure_families(db_session, brand.id)
    await db_session.commit()

    assert result["status"] == "completed"
    assert result["rows_processed"] >= 2

    reports = (await db_session.execute(
        select(FailureFamilyReport).where(FailureFamilyReport.brand_id == brand.id)
    )).scalars().all()
    assert len(reports) >= 2


@pytest.mark.asyncio
async def test_suppression_rules_for_threshold(db_session, brand_with_losers):
    brand = brand_with_losers
    result = await recompute_failure_families(db_session, brand.id)
    await db_session.commit()

    assert result["suppressed"] >= 1

    rules = (await db_session.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand.id, SuppressionRule.is_active.is_(True))
    )).scalars().all()
    assert len(rules) >= 1
    hook_rules = [r for r in rules if r.family_type == "hook_type"]
    assert len(hook_rules) >= 1
    assert hook_rules[0].suppression_mode in ("temporary", "persistent")


@pytest.mark.asyncio
async def test_below_threshold_not_suppressed(db_session, brand_with_losers):
    brand = brand_with_losers
    await recompute_failure_families(db_session, brand.id)
    await db_session.commit()

    rules = (await db_session.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand.id, SuppressionRule.is_active.is_(True))
    )).scalars().all()
    carousel_rules = [r for r in rules if r.family_key == "carousel"]
    assert len(carousel_rules) == 0


@pytest.mark.asyncio
async def test_members_persisted(db_session, brand_with_losers):
    brand = brand_with_losers
    await recompute_failure_families(db_session, brand.id)
    await db_session.commit()

    members = (await db_session.execute(
        select(FailureFamilyMember)
    )).scalars().all()
    assert len(members) >= 2


@pytest.mark.asyncio
async def test_decay_check(db_session, brand_with_losers):
    brand = brand_with_losers
    await recompute_failure_families(db_session, brand.id)
    await db_session.commit()
    result = await run_decay_check(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_list_reports(db_session, brand_with_losers):
    brand = brand_with_losers
    await recompute_failure_families(db_session, brand.id)
    await db_session.commit()
    reports = await list_reports(db_session, brand.id)
    assert len(reports) >= 2


@pytest.mark.asyncio
async def test_list_suppression_rules(db_session, brand_with_losers):
    brand = brand_with_losers
    await recompute_failure_families(db_session, brand.id)
    await db_session.commit()
    rules = await list_suppression_rules(db_session, brand.id)
    assert len(rules) >= 1


@pytest.mark.asyncio
async def test_get_active_for_downstream(db_session, brand_with_losers):
    brand = brand_with_losers
    await recompute_failure_families(db_session, brand.id)
    await db_session.commit()
    active = await get_active_suppressions_for_downstream(db_session, brand.id)
    assert isinstance(active, list)
    assert len(active) >= 1
    for a in active:
        assert "family_type" in a
        assert "family_key" in a


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_losers):
    brand = brand_with_losers
    r1 = await recompute_failure_families(db_session, brand.id)
    await db_session.commit()
    r2 = await recompute_failure_families(db_session, brand.id)
    await db_session.commit()
    assert r1["rows_processed"] == r2["rows_processed"]


def test_failure_family_worker_registered():
    import workers.failure_family_worker.tasks  # noqa: F401
    from workers.celery_app import app
    assert "workers.failure_family_worker.tasks.recompute_failure_families" in app.tasks
