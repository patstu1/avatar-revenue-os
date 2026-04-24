"""Integration: Phase C persistence (PostgreSQL via TEST_DATABASE_URL).

Run in Docker Compose or with a reachable Postgres matching tests/conftest.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from apps.api.services import market_timing_service, recovery_service, reputation_service
from packages.db.enums import JobStatus
from packages.db.models.core import Brand, Organization
from packages.db.models.market_timing import MacroSignalEvent, MarketTimingReport
from packages.db.models.recovery import RecoveryAction, RecoveryIncident
from packages.db.models.reputation import ReputationReport
from packages.db.models.system import SystemJob


@pytest.mark.asyncio
async def test_recovery_recompute_persists_incidents(db_session):
    org = Organization(name="Phase C Org", slug="phase-c-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(name="Phase C Brand", slug="phase-c-brand", organization_id=org.id)
    db_session.add(brand)
    await db_session.flush()

    for _ in range(40):
        db_session.add(
            SystemJob(
                brand_id=brand.id,
                job_name="publish_pipeline",
                job_type="publish",
                status=JobStatus.FAILED,
            )
        )
    for _ in range(60):
        db_session.add(
            SystemJob(
                brand_id=brand.id,
                job_name="publish_pipeline",
                job_type="publish",
                status=JobStatus.COMPLETED,
            )
        )
    await db_session.commit()

    out = await recovery_service.recompute_recovery_incidents(db_session, brand.id)
    await db_session.commit()
    assert out["incidents"] >= 1

    incidents = (
        (await db_session.execute(select(RecoveryIncident).where(RecoveryIncident.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(incidents) >= 1
    actions = (
        (await db_session.execute(select(RecoveryAction).where(RecoveryAction.brand_id == brand.id))).scalars().all()
    )
    assert len(actions) >= 1


@pytest.mark.asyncio
async def test_reputation_recompute_persists_report(db_session):
    org = Organization(name="Rep Org", slug="rep-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(name="Rep Brand", slug="rep-brand", niche="finance", organization_id=org.id)
    db_session.add(brand)
    await db_session.commit()

    out = await reputation_service.recompute_reputation(db_session, brand.id)
    await db_session.commit()
    assert out["reputation_reports"] == 1

    rows = (
        (await db_session.execute(select(ReputationReport).where(ReputationReport.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].primary_risks_json is not None


@pytest.mark.asyncio
async def test_market_timing_macro_changes_recommendation(db_session):
    org = Organization(name="MT Org", slug="mt-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(name="MT Brand", slug="mt-brand", niche="tech", organization_id=org.id)
    db_session.add(brand)
    await db_session.flush()

    db_session.add(
        MacroSignalEvent(
            brand_id=brand.id,
            signal_type="cpm_index",
            source_name="unit_test",
            signal_metadata_json={"value": 0.15},
            observed_at=None,
        )
    )
    await db_session.commit()

    await market_timing_service.recompute_market_timing(db_session, brand.id)
    await db_session.commit()
    first = (
        (await db_session.execute(select(MarketTimingReport).where(MarketTimingReport.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(first) >= 1
    cat_first = {r.market_category: r.timing_score for r in first}
    await db_session.execute(delete(MacroSignalEvent).where(MacroSignalEvent.brand_id == brand.id))
    await db_session.commit()

    db_session.add(
        MacroSignalEvent(
            brand_id=brand.id,
            signal_type="cpm_index",
            source_name="unit_test",
            signal_metadata_json={"value": 0.95},
            observed_at=None,
        )
    )
    await db_session.commit()

    await market_timing_service.recompute_market_timing(db_session, brand.id)
    await db_session.commit()
    second = (
        (await db_session.execute(select(MarketTimingReport).where(MarketTimingReport.brand_id == brand.id)))
        .scalars()
        .all()
    )
    cat_second = {r.market_category: r.timing_score for r in second}
    assert cat_first.get("cpm_friendly") != cat_second.get("cpm_friendly")
    assert sum(r.timing_score for r in first) != sum(r.timing_score for r in second)
