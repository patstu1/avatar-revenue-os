"""DB-backed integration tests for Promote-Winner Engine."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.promote_winner_service import (
    add_observation,
    create_experiment,
    evaluate_experiment,
    get_promoted_rules_for_brief,
    list_active_experiments,
    list_losers,
    list_promoted_rules,
    list_winners,
    run_decay_check,
)
from packages.db.models.core import Brand, Organization
from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory
from packages.db.models.promote_winner import (
    PromotedWinnerRule,
    PWExperimentLoser,
    PWExperimentVariant,
    PWExperimentWinner,
)


@pytest_asyncio.fixture
async def brand(db_session: AsyncSession):
    slug = f"pw-{uuid.uuid4().hex[:6]}"
    org = Organization(name="PW Test Org", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(organization_id=org.id, name="PW Brand", slug=slug, niche="tech")
    db_session.add(brand)
    await db_session.flush()
    return brand


@pytest.mark.asyncio
async def test_create_experiment(db_session, brand):
    exp = await create_experiment(
        db_session,
        brand.id,
        {
            "experiment_name": "Hook test",
            "hypothesis": "Curiosity hooks beat pain hooks",
            "tested_variable": "hook",
            "variant_configs": [{"name": "curiosity"}, {"name": "direct_pain"}],
            "primary_metric": "engagement_rate",
        },
    )
    await db_session.commit()
    assert exp.status == "active"
    assert exp.tested_variable == "hook"

    variants = (
        (await db_session.execute(select(PWExperimentVariant).where(PWExperimentVariant.experiment_id == exp.id)))
        .scalars()
        .all()
    )
    assert len(variants) == 2
    assert variants[0].is_control is True


@pytest.mark.asyncio
async def test_add_observations(db_session, brand):
    exp = await create_experiment(
        db_session,
        brand.id,
        {
            "experiment_name": "CTA test",
            "hypothesis": "Direct CTA beats soft CTA",
            "tested_variable": "cta_type",
            "variant_configs": [{"name": "direct"}, {"name": "soft"}],
        },
    )
    await db_session.flush()
    variants = (
        (await db_session.execute(select(PWExperimentVariant).where(PWExperimentVariant.experiment_id == exp.id)))
        .scalars()
        .all()
    )

    for _ in range(35):
        await add_observation(db_session, exp.id, variants[0].id, "engagement_rate", 0.15)
        await add_observation(db_session, exp.id, variants[1].id, "engagement_rate", 0.05)
    await db_session.commit()

    v0 = (
        await db_session.execute(select(PWExperimentVariant).where(PWExperimentVariant.id == variants[0].id))
    ).scalar_one()
    assert v0.sample_count == 35


@pytest.mark.asyncio
async def test_evaluate_finds_winner(db_session, brand):
    exp = await create_experiment(
        db_session,
        brand.id,
        {
            "experiment_name": "Offer angle test",
            "hypothesis": "Premium angle beats budget angle",
            "tested_variable": "offer_angle",
            "variant_configs": [{"name": "premium"}, {"name": "budget"}],
            "min_sample_size": 30,
            "confidence_threshold": 0.80,
        },
    )
    await db_session.flush()
    variants = (
        (await db_session.execute(select(PWExperimentVariant).where(PWExperimentVariant.experiment_id == exp.id)))
        .scalars()
        .all()
    )

    for _ in range(50):
        await add_observation(db_session, exp.id, variants[0].id, "engagement_rate", 0.18)
        await add_observation(db_session, exp.id, variants[1].id, "engagement_rate", 0.04)
    await db_session.flush()

    result = await evaluate_experiment(db_session, exp.id)
    await db_session.commit()

    assert result["status"] == "winner_found"
    assert result["confidence"] >= 0.80

    winners = (
        (await db_session.execute(select(PWExperimentWinner).where(PWExperimentWinner.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(winners) == 1
    assert winners[0].promoted is True

    rules = (
        (await db_session.execute(select(PromotedWinnerRule).where(PromotedWinnerRule.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(rules) >= 1
    assert any(r.rule_type == "default_offer_angle" for r in rules)

    losers = (
        (await db_session.execute(select(PWExperimentLoser).where(PWExperimentLoser.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(losers) == 1
    assert losers[0].suppressed is True


@pytest.mark.asyncio
async def test_winner_feeds_pattern_memory(db_session, brand):
    exp = await create_experiment(
        db_session,
        brand.id,
        {
            "experiment_name": "Hook PM test",
            "hypothesis": "Test hook for pattern memory",
            "tested_variable": "hook",
            "variant_configs": [{"name": "authority_led"}, {"name": "comparison"}],
            "min_sample_size": 30,
            "confidence_threshold": 0.80,
        },
    )
    await db_session.flush()
    variants = (
        (await db_session.execute(select(PWExperimentVariant).where(PWExperimentVariant.experiment_id == exp.id)))
        .scalars()
        .all()
    )
    for _ in range(50):
        await add_observation(db_session, exp.id, variants[0].id, "engagement_rate", 0.20)
        await add_observation(db_session, exp.id, variants[1].id, "engagement_rate", 0.03)
    await db_session.flush()
    await evaluate_experiment(db_session, exp.id)
    await db_session.commit()

    wpm = (
        (
            await db_session.execute(
                select(WinningPatternMemory).where(
                    WinningPatternMemory.brand_id == brand.id,
                    WinningPatternMemory.pattern_type == "hook",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(wpm) >= 1

    lpm = (
        (
            await db_session.execute(
                select(LosingPatternMemory).where(
                    LosingPatternMemory.brand_id == brand.id,
                    LosingPatternMemory.pattern_type == "hook",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(lpm) >= 1


@pytest.mark.asyncio
async def test_decay_check(db_session, brand):
    result = await run_decay_check(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_list_helpers(db_session, brand):
    assert isinstance(await list_active_experiments(db_session, brand.id), list)
    assert isinstance(await list_winners(db_session, brand.id), list)
    assert isinstance(await list_losers(db_session, brand.id), list)
    assert isinstance(await list_promoted_rules(db_session, brand.id), list)


@pytest.mark.asyncio
async def test_promoted_rules_for_brief(db_session, brand):
    rules = await get_promoted_rules_for_brief(db_session, brand.id, "tiktok")
    assert isinstance(rules, list)


@pytest.mark.asyncio
async def test_insufficient_sample_reported(db_session, brand):
    exp = await create_experiment(
        db_session,
        brand.id,
        {
            "experiment_name": "Small test",
            "hypothesis": "Too few samples",
            "tested_variable": "content_form",
            "variant_configs": [{"name": "short"}, {"name": "long"}],
            "min_sample_size": 100,
        },
    )
    await db_session.flush()
    variants = (
        (await db_session.execute(select(PWExperimentVariant).where(PWExperimentVariant.experiment_id == exp.id)))
        .scalars()
        .all()
    )
    for _ in range(5):
        await add_observation(db_session, exp.id, variants[0].id, "engagement_rate", 0.10)
    await db_session.flush()

    result = await evaluate_experiment(db_session, exp.id)
    await db_session.commit()
    assert result["status"] == "insufficient_sample"
    assert result["progress_pct"] < 100


def test_promote_winner_worker_registered():
    import workers.promote_winner_worker.tasks  # noqa: F401
    from workers.celery_app import app

    assert "workers.promote_winner_worker.tasks.evaluate_and_promote" in app.tasks
