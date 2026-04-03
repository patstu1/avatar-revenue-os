"""API routers for Live Execution Closure Phase 1."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from apps.api.deps import CurrentUser, DBSession, require_brand_access
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.live_execution import (
    AnalyticsEventOut,
    AnalyticsImportCreate,
    AnalyticsImportOut,
    ConversionEventOut,
    ConversionImportCreate,
    ConversionImportOut,
    CrmContactCreate,
    CrmContactOut,
    CrmSyncOut,
    EmailSendCreate,
    EmailSendOut,
    ExperimentLiveResultOut,
    ExperimentObservationImportCreate,
    ExperimentObservationImportOut,
    MessagingBlockerOut,
    RecomputeSummaryOut,
    SmsSendCreate,
    SmsSendOut,
)
from apps.api.services import live_execution_service as svc

router = APIRouter()


# ── Analytics / Attribution ────────────────────────────────────────────

@router.get("/{brand_id}/analytics-imports", response_model=list[AnalyticsImportOut])
async def get_analytics_imports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_analytics_imports(db, brand_id)


@router.post("/{brand_id}/analytics-imports", response_model=RecomputeSummaryOut)
async def post_analytics_import(
    brand_id: uuid.UUID, body: AnalyticsImportCreate,
    current_user: CurrentUser, db: DBSession, _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.create_analytics_import(db, brand_id, body.source, body.source_category, body.events)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/analytics-events", response_model=list[AnalyticsEventOut])
async def get_analytics_events(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_analytics_events(db, brand_id)


@router.post("/{brand_id}/analytics-events/recompute", response_model=RecomputeSummaryOut)
async def recompute_analytics(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.recompute_analytics(db, brand_id)
    return RecomputeSummaryOut(**result)


# ── Conversions ────────────────────────────────────────────────────────

@router.get("/{brand_id}/conversion-imports", response_model=list[ConversionImportOut])
async def get_conversion_imports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_conversion_imports(db, brand_id)


@router.post("/{brand_id}/conversion-imports", response_model=RecomputeSummaryOut)
async def post_conversion_import(
    brand_id: uuid.UUID, body: ConversionImportCreate,
    current_user: CurrentUser, db: DBSession, _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.create_conversion_import(db, brand_id, body.source, body.source_category, body.conversions)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/conversion-events", response_model=list[ConversionEventOut])
async def get_conversion_events(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_conversion_events(db, brand_id)


@router.post("/{brand_id}/conversion-events/recompute", response_model=RecomputeSummaryOut)
async def recompute_conversions(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.recompute_conversions(db, brand_id)
    return RecomputeSummaryOut(**result)


# ── Experiment Truth ───────────────────────────────────────────────────

@router.get("/{brand_id}/experiment-observation-imports", response_model=list[ExperimentObservationImportOut])
async def get_experiment_imports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_experiment_imports(db, brand_id)


@router.post("/{brand_id}/experiment-observation-imports", response_model=RecomputeSummaryOut)
async def post_experiment_observation_import(
    brand_id: uuid.UUID, body: ExperimentObservationImportCreate,
    current_user: CurrentUser, db: DBSession, _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.create_experiment_observation_import(db, brand_id, body.source, body.observations)
    return RecomputeSummaryOut(**result)


@router.get("/{brand_id}/experiment-live-results", response_model=list[ExperimentLiveResultOut])
async def get_experiment_live_results(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_experiment_live_results(db, brand_id)


@router.post("/{brand_id}/experiment-live-results/recompute", response_model=RecomputeSummaryOut)
async def recompute_experiment_truth(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.recompute_experiment_truth(db, brand_id)
    return RecomputeSummaryOut(**result)


# ── CRM / Contacts ────────────────────────────────────────────────────

@router.get("/{brand_id}/crm-contacts", response_model=list[CrmContactOut])
async def get_crm_contacts(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_crm_contacts(db, brand_id)


@router.post("/{brand_id}/crm-contacts", response_model=CrmContactOut)
async def post_crm_contact(brand_id: uuid.UUID, body: CrmContactCreate, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.create_crm_contact(db, brand_id, body.model_dump())


@router.get("/{brand_id}/crm-syncs", response_model=list[CrmSyncOut])
async def get_crm_syncs(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_crm_syncs(db, brand_id)


@router.post("/{brand_id}/crm-syncs/recompute", response_model=RecomputeSummaryOut)
async def run_crm_sync(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.run_crm_sync(db, brand_id)
    return RecomputeSummaryOut(created=result["created"], updated=result["updated"], details=result.get("details"))


# ── Email ──────────────────────────────────────────────────────────────

@router.get("/{brand_id}/email-send-requests", response_model=list[EmailSendOut])
async def get_email_requests(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_email_requests(db, brand_id)


@router.post("/{brand_id}/email-send-requests", response_model=EmailSendOut)
async def post_email_send(brand_id: uuid.UUID, body: EmailSendCreate, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.create_email_send(db, brand_id, body.model_dump())


# ── SMS ────────────────────────────────────────────────────────────────

@router.get("/{brand_id}/sms-send-requests", response_model=list[SmsSendOut])
async def get_sms_requests(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_sms_requests(db, brand_id)


@router.post("/{brand_id}/sms-send-requests", response_model=SmsSendOut)
async def post_sms_send(brand_id: uuid.UUID, body: SmsSendCreate, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.create_sms_send(db, brand_id, body.model_dump())


# ── Messaging Blockers ────────────────────────────────────────────────

@router.get("/{brand_id}/messaging-blockers", response_model=list[MessagingBlockerOut])
async def get_messaging_blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_messaging_blockers(db, brand_id)


@router.post("/{brand_id}/messaging-blockers/recompute", response_model=RecomputeSummaryOut)
async def recompute_messaging_blockers(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await require_brand_access(brand_id, current_user, db)
    result = await svc.recompute_messaging_blockers(db, brand_id)
    return RecomputeSummaryOut(**result)
