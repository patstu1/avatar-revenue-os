"""API routers for Live Execution Phase 2 + Buffer Expansion."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.live_execution_phase2 import (
    AdReportingImportOut,
    BufferCapabilityCheckOut,
    BufferExecutionTruthOut,
    BufferRetryRecordOut,
    ExternalEventIngestionOut,
    PaymentConnectorSyncOut,
    PlatformAnalyticsSyncOut,
    RecomputeSummaryOut,
    SequenceTriggerActionOut,
    WebhookEventCreate,
    WebhookEventOut,
)
from apps.api.services import live_execution_phase2_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


# ── Webhook Events ─────────────────────────────────────────────────────

@router.post("/{brand_id}/webhook-events", response_model=RecomputeSummaryOut)
async def ingest_webhook(
    brand_id: uuid.UUID, body: WebhookEventCreate,
    current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.ingest_webhook_event(db, brand_id, body.model_dump())
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/webhook-events", response_model=list[WebhookEventOut])
async def list_webhook_events(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_webhook_events(db, brand_id)


# ── Event Ingestions ───────────────────────────────────────────────────

@router.get("/{brand_id}/event-ingestions", response_model=list[ExternalEventIngestionOut])
async def list_event_ingestions(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_event_ingestions(db, brand_id)


@router.post("/{brand_id}/event-ingestions/recompute", response_model=RecomputeSummaryOut)
async def recompute_event_ingestions(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_event_ingestions(db, brand_id)
    return RecomputeSummaryOut(**result)


# ── Sequence Triggers ──────────────────────────────────────────────────

@router.get("/{brand_id}/sequence-triggers", response_model=list[SequenceTriggerActionOut])
async def list_sequence_triggers(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_sequence_triggers(db, brand_id)


@router.post("/{brand_id}/sequence-triggers/process", response_model=RecomputeSummaryOut)
async def process_sequence_triggers(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.process_sequence_triggers(db, brand_id)
    return RecomputeSummaryOut(**result)


# ── Payment Syncs ─────────────────────────────────────────────────────

@router.get("/{brand_id}/payment-syncs", response_model=list[PaymentConnectorSyncOut])
async def list_payment_syncs(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_payment_syncs(db, brand_id)


@router.post("/{brand_id}/payment-syncs/run", response_model=RecomputeSummaryOut)
async def run_payment_sync(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    provider: str = Query("stripe"),
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.run_payment_sync(db, brand_id, provider=provider)
    return RecomputeSummaryOut(**result)


# ── Analytics Syncs ───────────────────────────────────────────────────

@router.get("/{brand_id}/analytics-syncs", response_model=list[PlatformAnalyticsSyncOut])
async def list_analytics_syncs(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_analytics_syncs(db, brand_id)


@router.post("/{brand_id}/analytics-syncs/run", response_model=RecomputeSummaryOut)
async def run_analytics_sync(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    source: str = Query("buffer"),
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.run_analytics_sync(db, brand_id, source=source)
    return RecomputeSummaryOut(**result)


# ── Ad Imports ────────────────────────────────────────────────────────

@router.get("/{brand_id}/ad-imports", response_model=list[AdReportingImportOut])
async def list_ad_imports(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_ad_imports(db, brand_id)


@router.post("/{brand_id}/ad-imports/run", response_model=RecomputeSummaryOut)
async def run_ad_import(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    platform: str = Query("meta_ads"),
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.run_ad_import(db, brand_id, platform=platform)
    return RecomputeSummaryOut(**result)


# ── Buffer Execution Truth ────────────────────────────────────────────

@router.get("/{brand_id}/buffer-execution-truth", response_model=list[BufferExecutionTruthOut])
async def list_buffer_execution_truth(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_buffer_execution_truth(db, brand_id)


@router.post("/{brand_id}/buffer-execution-truth/recompute", response_model=RecomputeSummaryOut)
async def recompute_buffer_execution_truth(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_buffer_execution_truth(db, brand_id)
    return RecomputeSummaryOut(**result)


# ── Buffer Retries ────────────────────────────────────────────────────

@router.get("/{brand_id}/buffer-retries", response_model=list[BufferRetryRecordOut])
async def list_buffer_retries(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_buffer_retries(db, brand_id)


@router.post("/{brand_id}/buffer-retries/recompute", response_model=RecomputeSummaryOut)
async def recompute_buffer_retries(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_buffer_retries(db, brand_id)
    return RecomputeSummaryOut(**result)


# ── Buffer Capabilities ──────────────────────────────────────────────

@router.get("/{brand_id}/buffer-capabilities", response_model=list[BufferCapabilityCheckOut])
async def list_buffer_capabilities(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_buffer_capabilities(db, brand_id)


@router.post("/{brand_id}/buffer-capabilities/recompute", response_model=RecomputeSummaryOut)
async def recompute_buffer_capabilities(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_buffer_capabilities(db, brand_id)
    return RecomputeSummaryOut(**result)
