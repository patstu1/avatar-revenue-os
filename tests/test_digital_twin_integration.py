"""DB-backed integration tests for Digital Twin."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.digital_twin_service import (
    get_top_recommendations,
    list_recommendations,
    list_runs,
    list_scenarios,
    run_simulation,
)
from packages.db.enums import Platform
from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand, Organization
from packages.db.models.digital_twin import SimulationRecommendation, SimulationRun, SimulationScenario


@pytest_asyncio.fixture
async def brand_with_state(db_session: AsyncSession):
    slug = f"dt-{uuid.uuid4().hex[:6]}"
    org = Organization(name="DT Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()
    brand = Brand(organization_id=org.id, name="DT Brand", slug=slug, niche="tech")
    db_session.add(brand); await db_session.flush()
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username=f"@dt_{slug}")
    db_session.add(acct); await db_session.flush()
    db_session.add(AccountStateReport(brand_id=brand.id, account_id=acct.id, current_state="scaling", confidence=0.8, monetization_intensity="medium", posting_cadence="aggressive", expansion_eligible=True))
    await db_session.flush()
    return brand


@pytest.mark.asyncio
async def test_run_simulation(db_session, brand_with_state):
    brand = brand_with_state
    result = await run_simulation(db_session, brand.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] >= 2
    assert result["recommendations"] >= 1


@pytest.mark.asyncio
async def test_run_created(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    runs = (await db_session.execute(select(SimulationRun).where(SimulationRun.brand_id == brand.id))).scalars().all()
    assert len(runs) == 1
    assert runs[0].scenario_count >= 2


@pytest.mark.asyncio
async def test_scenarios_created(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    scenarios = (await db_session.execute(select(SimulationScenario).join(SimulationRun).where(SimulationRun.brand_id == brand.id))).scalars().all()
    assert len(scenarios) >= 2
    recommended = [s for s in scenarios if s.is_recommended]
    assert len(recommended) >= 1


@pytest.mark.asyncio
async def test_recommendations_created(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    recs = (await db_session.execute(select(SimulationRecommendation).where(SimulationRecommendation.brand_id == brand.id))).scalars().all()
    assert len(recs) >= 1
    for r in recs:
        assert r.recommended_action
        assert r.expected_profit_delta >= 0


@pytest.mark.asyncio
async def test_list_runs(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    runs = await list_runs(db_session, brand.id)
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_list_scenarios(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    s = await list_scenarios(db_session, brand.id)
    assert len(s) >= 2


@pytest.mark.asyncio
async def test_list_recommendations(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    r = await list_recommendations(db_session, brand.id)
    assert len(r) >= 1


@pytest.mark.asyncio
async def test_get_top_recommendations(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    top = await get_top_recommendations(db_session, brand.id)
    assert isinstance(top, list)
    assert len(top) >= 1
    for t in top:
        assert "action" in t
        assert "delta" in t


@pytest.mark.asyncio
async def test_idempotent(db_session, brand_with_state):
    brand = brand_with_state
    await run_simulation(db_session, brand.id); await db_session.commit()
    await run_simulation(db_session, brand.id); await db_session.commit()
    runs = (await db_session.execute(select(SimulationRun).where(SimulationRun.brand_id == brand.id))).scalars().all()
    assert len(runs) == 1


def test_digital_twin_worker_registered():
    import workers.digital_twin_worker.tasks  # noqa: F401
    from workers.celery_app import app
    assert "workers.digital_twin_worker.tasks.run_simulations" in app.tasks
