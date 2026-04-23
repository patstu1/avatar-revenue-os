"""DB-backed integration tests for Live Execution Closure Phase 1."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand, Organization
from packages.db.models.live_execution import (
    AnalyticsEvent,
    AnalyticsImport,
    ConversionEvent,
    ConversionImport,
    CrmContact,
    CrmSync,
    EmailSendRequest,
    ExperimentLiveResult,
    ExperimentObservationImport,
    MessagingBlocker,
    SmsSendRequest,
)

BRAND_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


@pytest_asyncio.fixture
async def seed_brand(db_session: AsyncSession):
    org = Organization(name="LEC Test Org", slug="lec-test-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(id=BRAND_ID, name="LEC Test Brand", slug="lec-test-brand", organization_id=org.id)
    db_session.add(brand)
    await db_session.commit()
    return brand


@pytest.mark.asyncio
async def test_analytics_import_creates_events(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import create_analytics_import

    result = await create_analytics_import(db_session, BRAND_ID, "buffer_analytics", "social", [
        {"event_type": "view", "platform": "tiktok", "external_post_id": "abc123", "metric_value": 500},
        {"event_type": "engagement", "platform": "instagram", "external_post_id": "def456", "metric_value": 120},
    ])
    assert result["created"] == 2

    imports = list((await db_session.execute(
        select(AnalyticsImport).where(AnalyticsImport.brand_id == BRAND_ID)
    )).scalars().all())
    assert len(imports) == 1
    assert imports[0].events_imported == 2

    events = list((await db_session.execute(
        select(AnalyticsEvent).where(AnalyticsEvent.brand_id == BRAND_ID)
    )).scalars().all())
    assert len(events) == 2
    assert all(e.truth_level == "live_import" for e in events)


@pytest.mark.asyncio
async def test_conversion_import_calculates_profit(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import create_conversion_import

    result = await create_conversion_import(db_session, BRAND_ID, "stripe_payments", "checkout", [
        {"conversion_type": "purchase", "revenue": 100.0, "cost": 20.0, "external_order_id": "ord_1"},
        {"conversion_type": "subscription", "revenue": 50.0, "cost": 5.0},
    ])
    assert result["created"] == 2

    events = list((await db_session.execute(
        select(ConversionEvent).where(ConversionEvent.brand_id == BRAND_ID)
    )).scalars().all())
    assert len(events) == 2
    profits = [e.profit for e in events]
    assert 80.0 in profits
    assert 45.0 in profits


@pytest.mark.asyncio
async def test_experiment_observation_import(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import create_experiment_observation_import

    result = await create_experiment_observation_import(db_session, BRAND_ID, "google_analytics", [
        {"observation_type": "conversion", "metric_name": "ctr", "metric_value": 0.045, "sample_size": 200, "confidence": 0.92},
    ])
    assert result["created"] == 1

    results = list((await db_session.execute(
        select(ExperimentLiveResult).where(ExperimentLiveResult.brand_id == BRAND_ID)
    )).scalars().all())
    assert len(results) == 1
    assert results[0].truth_level == "live_import"
    assert results[0].confidence == 0.92


@pytest.mark.asyncio
async def test_crm_contact_creation_and_sync_blocked(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import create_crm_contact, run_crm_sync

    contact = await create_crm_contact(db_session, BRAND_ID, {
        "email": "test@example.com", "name": "Test User", "lifecycle_stage": "lead",
    })
    assert contact.email == "test@example.com"
    assert contact.sync_status == "pending"

    result = await run_crm_sync(db_session, BRAND_ID)
    assert result["created"] == 0

    syncs = list((await db_session.execute(
        select(CrmSync).where(CrmSync.brand_id == BRAND_ID)
    )).scalars().all())
    assert len(syncs) == 1
    assert syncs[0].status == "blocked"


@pytest.mark.asyncio
async def test_email_send_fails_without_provider(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import create_email_send

    req = await create_email_send(db_session, BRAND_ID, {
        "to_email": "user@example.com",
        "subject": "Test Subject",
        "body_text": "Hello world",
    })
    assert req.status == "failed"
    assert "No email provider" in req.error_message


@pytest.mark.asyncio
async def test_sms_send_fails_without_api_key(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import create_sms_send

    req = await create_sms_send(db_session, BRAND_ID, {
        "to_phone": "+15551234567",
        "message_body": "Test SMS message",
    })
    assert req.status == "failed"
    assert "No SMS provider" in req.error_message


@pytest.mark.asyncio
async def test_messaging_blockers_detected(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import recompute_messaging_blockers

    result = await recompute_messaging_blockers(db_session, BRAND_ID)
    assert result["created"] >= 4

    blockers = list((await db_session.execute(
        select(MessagingBlocker).where(
            MessagingBlocker.brand_id == BRAND_ID,
            MessagingBlocker.is_active.is_(True),
        )
    )).scalars().all())
    types = {b.blocker_type for b in blockers}
    assert "missing_smtp_config" in types
    assert "missing_sms_api_key" in types
    assert "no_contacts" in types


@pytest.mark.asyncio
async def test_analytics_truth_reconciliation(db_session: AsyncSession, seed_brand):
    from apps.api.services.live_execution_service import create_analytics_import, recompute_analytics

    await create_analytics_import(db_session, BRAND_ID, "tiktok_insights", "social", [
        {"event_type": "view", "platform": "tiktok", "metric_value": 1000},
    ])

    result = await recompute_analytics(db_session, BRAND_ID)
    assert isinstance(result, dict)

    events = list((await db_session.execute(
        select(AnalyticsEvent).where(AnalyticsEvent.brand_id == BRAND_ID)
    )).scalars().all())
    assert all(e.truth_level == "live_import" for e in events)
