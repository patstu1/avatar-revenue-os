"""Service layer for Live Execution Closure Phase 1."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

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
from packages.scoring.live_execution_engine import (
    classify_analytics_source,
    compute_import_summary,
    detect_messaging_blockers,
    reconcile_truth,
    validate_email_send,
    validate_sms_send,
)


# ── A. Analytics / Attribution ─────────────────────────────────────────

async def list_analytics_imports(db: AsyncSession, brand_id: uuid.UUID) -> list[AnalyticsImport]:
    q = select(AnalyticsImport).where(
        AnalyticsImport.brand_id == brand_id,
        AnalyticsImport.is_active.is_(True),
    ).order_by(AnalyticsImport.created_at.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def list_analytics_events(db: AsyncSession, brand_id: uuid.UUID) -> list[AnalyticsEvent]:
    q = select(AnalyticsEvent).where(
        AnalyticsEvent.brand_id == brand_id,
        AnalyticsEvent.is_active.is_(True),
    ).order_by(AnalyticsEvent.created_at.desc()).limit(200)
    return list((await db.execute(q)).scalars().all())


async def create_analytics_import(
    db: AsyncSession, brand_id: uuid.UUID, source: str, source_category: str, events: list[dict[str, Any]],
) -> dict[str, int]:
    cat = classify_analytics_source(source)
    if source_category == "social":
        source_category = cat

    existing_ext_ids: set[str] = set()
    q = select(AnalyticsEvent.external_post_id).where(
        AnalyticsEvent.brand_id == brand_id,
        AnalyticsEvent.external_post_id.isnot(None),
    )
    for row in (await db.execute(q)).scalars().all():
        existing_ext_ids.add(row)

    summary = compute_import_summary(events, existing_ext_ids)

    imp = AnalyticsImport(
        brand_id=brand_id,
        source=source,
        source_category=source_category,
        events_imported=summary["events_imported"],
        events_matched=summary["events_matched"],
        events_new=summary["events_new"],
    )
    db.add(imp)
    await db.flush()

    for ev in events:
        ae = AnalyticsEvent(
            brand_id=brand_id,
            import_id=imp.id,
            source=source,
            event_type=ev.get("event_type", "engagement"),
            platform=ev.get("platform"),
            external_post_id=ev.get("external_post_id"),
            metric_value=ev.get("metric_value", 0.0),
            truth_level="live_import",
        )
        db.add(ae)

    await db.commit()
    return {"created": summary["events_new"], "updated": summary["events_matched"]}


async def recompute_analytics(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    """Reconcile truth levels for existing analytics events."""
    q = select(AnalyticsEvent).where(AnalyticsEvent.brand_id == brand_id, AnalyticsEvent.is_active.is_(True))
    events = list((await db.execute(q)).scalars().all())
    updated = 0
    for ev in events:
        new_level = reconcile_truth(ev.truth_level, "live_import" if ev.import_id else "synthetic_proxy")
        if new_level != ev.truth_level:
            ev.truth_level = new_level
            updated += 1
    await db.commit()
    return {"created": 0, "updated": updated}


# ── Conversions ────────────────────────────────────────────────────────

async def list_conversion_imports(db: AsyncSession, brand_id: uuid.UUID) -> list[ConversionImport]:
    q = select(ConversionImport).where(
        ConversionImport.brand_id == brand_id,
        ConversionImport.is_active.is_(True),
    ).order_by(ConversionImport.created_at.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def list_conversion_events(db: AsyncSession, brand_id: uuid.UUID) -> list[ConversionEvent]:
    q = select(ConversionEvent).where(
        ConversionEvent.brand_id == brand_id,
        ConversionEvent.is_active.is_(True),
    ).order_by(ConversionEvent.created_at.desc()).limit(200)
    return list((await db.execute(q)).scalars().all())


async def create_conversion_import(
    db: AsyncSession, brand_id: uuid.UUID, source: str, source_category: str, conversions: list[dict[str, Any]],
) -> dict[str, int]:
    cat = classify_analytics_source(source)
    if source_category == "checkout":
        source_category = cat if cat != "manual" else "checkout"

    total_revenue = sum(c.get("revenue", 0.0) for c in conversions)

    imp = ConversionImport(
        brand_id=brand_id,
        source=source,
        source_category=source_category,
        conversions_imported=len(conversions),
        revenue_imported=total_revenue,
    )
    db.add(imp)
    await db.flush()

    for c in conversions:
        rev = c.get("revenue", 0.0)
        cost = c.get("cost", 0.0)
        content_item_id = None
        if c.get("content_item_id"):
            try:
                content_item_id = uuid.UUID(str(c["content_item_id"]))
            except (ValueError, AttributeError):
                logger.debug("conversion_content_item_id_parse_failed", exc_info=True)
        offer_id = None
        if c.get("offer_id"):
            try:
                offer_id = uuid.UUID(str(c["offer_id"]))
            except (ValueError, AttributeError):
                logger.debug("conversion_offer_id_parse_failed", exc_info=True)
        ce = ConversionEvent(
            brand_id=brand_id,
            import_id=imp.id,
            content_item_id=content_item_id,
            offer_id=offer_id,
            source=source,
            conversion_type=c.get("conversion_type", "purchase"),
            revenue=rev,
            cost=cost,
            profit=rev - cost,
            currency=c.get("currency", "USD"),
            external_order_id=c.get("external_order_id"),
            truth_level="live_import",
        )
        db.add(ce)

    await db.commit()
    return {"created": len(conversions), "updated": 0}


async def recompute_conversions(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    q = select(ConversionEvent).where(ConversionEvent.brand_id == brand_id, ConversionEvent.is_active.is_(True))
    events = list((await db.execute(q)).scalars().all())
    updated = 0
    for ev in events:
        new_level = reconcile_truth(ev.truth_level, "live_import" if ev.import_id else "synthetic_proxy")
        if new_level != ev.truth_level:
            ev.truth_level = new_level
            updated += 1
    await db.commit()
    return {"created": 0, "updated": updated}


# ── B. Experiment Truth ────────────────────────────────────────────────

async def list_experiment_imports(db: AsyncSession, brand_id: uuid.UUID) -> list[ExperimentObservationImport]:
    q = select(ExperimentObservationImport).where(
        ExperimentObservationImport.brand_id == brand_id,
        ExperimentObservationImport.is_active.is_(True),
    ).order_by(ExperimentObservationImport.created_at.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def list_experiment_live_results(db: AsyncSession, brand_id: uuid.UUID) -> list[ExperimentLiveResult]:
    q = select(ExperimentLiveResult).where(
        ExperimentLiveResult.brand_id == brand_id,
        ExperimentLiveResult.is_active.is_(True),
    ).order_by(ExperimentLiveResult.created_at.desc()).limit(200)
    return list((await db.execute(q)).scalars().all())


async def create_experiment_observation_import(
    db: AsyncSession, brand_id: uuid.UUID, source: str, observations: list[dict[str, Any]],
) -> dict[str, int]:
    matched = 0

    imp = ExperimentObservationImport(
        brand_id=brand_id,
        source=source,
        observations_imported=len(observations),
    )
    db.add(imp)
    await db.flush()

    for obs in observations:
        experiment_id = obs.get("experiment_id")
        variant_id = obs.get("variant_id")
        if experiment_id:
            matched += 1
        lr = ExperimentLiveResult(
            brand_id=brand_id,
            import_id=imp.id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            source=source,
            observation_type=obs.get("observation_type", "engagement"),
            metric_name=obs.get("metric_name", "value"),
            metric_value=obs.get("metric_value", 0.0),
            sample_size=obs.get("sample_size", 0),
            confidence=obs.get("confidence", 0.0),
            truth_level="live_import",
        )
        db.add(lr)

    imp.observations_matched = matched
    await db.commit()
    return {"created": len(observations), "updated": 0}


async def recompute_experiment_truth(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    q = select(ExperimentLiveResult).where(
        ExperimentLiveResult.brand_id == brand_id,
        ExperimentLiveResult.is_active.is_(True),
    )
    results = list((await db.execute(q)).scalars().all())
    updated = 0
    for r in results:
        new_level = reconcile_truth(r.truth_level, "live_import" if r.import_id else "synthetic_proxy")
        if new_level != r.truth_level:
            r.previous_truth_level = r.truth_level
            r.truth_level = new_level
            updated += 1
    await db.commit()
    return {"created": 0, "updated": updated}


# ── C. CRM / Contacts ─────────────────────────────────────────────────

async def list_crm_contacts(db: AsyncSession, brand_id: uuid.UUID) -> list[CrmContact]:
    q = select(CrmContact).where(
        CrmContact.brand_id == brand_id,
        CrmContact.is_active.is_(True),
    ).order_by(CrmContact.created_at.desc()).limit(200)
    return list((await db.execute(q)).scalars().all())


async def create_crm_contact(db: AsyncSession, brand_id: uuid.UUID, data: dict[str, Any]) -> CrmContact:
    c = CrmContact(
        brand_id=brand_id,
        email=data.get("email"),
        phone=data.get("phone"),
        name=data.get("name"),
        segment=data.get("segment"),
        lifecycle_stage=data.get("lifecycle_stage", "subscriber"),
        source=data.get("source", "manual"),
        tags_json=data.get("tags", []),
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def list_crm_syncs(db: AsyncSession, brand_id: uuid.UUID) -> list[CrmSync]:
    q = select(CrmSync).where(
        CrmSync.brand_id == brand_id,
        CrmSync.is_active.is_(True),
    ).order_by(CrmSync.created_at.desc()).limit(50)
    return list((await db.execute(q)).scalars().all())


async def run_crm_sync(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    has_crm = bool(os.environ.get("CRM_API_KEY"))

    contacts_q = select(CrmContact).where(
        CrmContact.brand_id == brand_id,
        CrmContact.is_active.is_(True),
        CrmContact.sync_status == "pending",
    )
    pending = list((await db.execute(contacts_q)).scalars().all())

    synced = 0
    failed = 0
    for c in pending:
        if has_crm:
            c.sync_status = "synced"
            synced += 1
        else:
            c.sync_status = "blocked"
            failed += 1

    sync_record = CrmSync(
        brand_id=brand_id,
        provider=os.environ.get("CRM_PROVIDER", "none"),
        direction="push",
        contacts_synced=synced,
        contacts_created=synced,
        contacts_updated=0,
        contacts_failed=failed,
        status="completed" if has_crm else "blocked",
        error_message=None if has_crm else "CRM_API_KEY not configured",
    )
    db.add(sync_record)
    await db.commit()
    return {"created": synced, "updated": 0, "details": f"synced={synced}, failed={failed}"}


# ── Email ──────────────────────────────────────────────────────────────

async def list_email_requests(db: AsyncSession, brand_id: uuid.UUID) -> list[EmailSendRequest]:
    q = select(EmailSendRequest).where(
        EmailSendRequest.brand_id == brand_id,
        EmailSendRequest.is_active.is_(True),
    ).order_by(EmailSendRequest.created_at.desc()).limit(200)
    return list((await db.execute(q)).scalars().all())


async def create_email_send(db: AsyncSession, brand_id: uuid.UUID, data: dict[str, Any]) -> EmailSendRequest:
    # Validate against the org's system-managed SMTP config (DB-first).
    # Env is only read by SmtpEmailClient.resolve() as a clearly-marked legacy fallback.
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.core import Brand
    org_id = (await db.execute(
        select(Brand.organization_id).where(Brand.id == brand_id)
    )).scalar_one_or_none()
    has_smtp = False
    if org_id:
        client = await SmtpEmailClient.resolve(db, org_id)
        has_smtp = client._is_configured()
    brand_ctx = {
        "has_smtp_config": has_smtp,
        "has_esp_api_key": bool(os.environ.get("ESP_API_KEY")),  # legacy env — to migrate next
    }
    validation = validate_email_send(data, brand_ctx)

    req = EmailSendRequest(
        brand_id=brand_id,
        contact_id=data.get("contact_id"),
        to_email=data["to_email"],
        subject=data["subject"],
        body_html=data.get("body_html"),
        body_text=data.get("body_text"),
        template_id=data.get("template_id"),
        sequence_step=data.get("sequence_step"),
        provider=data.get("provider", "smtp"),
        status="queued" if validation["valid"] else "failed",
        error_message=validation.get("error"),
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


async def execute_pending_emails(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    """Send pending EmailSendRequests for a brand.

    SMTP is resolved DB-first via ``SmtpEmailClient.resolve`` against the brand's
    organization. Env is only used as a legacy fallback inside the resolver;
    it is not the primary runtime path.
    """
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.core import Brand

    org_id = (await db.execute(
        select(Brand.organization_id).where(Brand.id == brand_id)
    )).scalar_one_or_none()

    if not org_id:
        return {"created": 0, "updated": 0, "details": "brand_not_found_or_no_org"}

    client = await SmtpEmailClient.resolve(db, org_id)
    smtp_ready = client._is_configured()

    q = select(EmailSendRequest).where(
        EmailSendRequest.brand_id == brand_id,
        EmailSendRequest.is_active.is_(True),
        EmailSendRequest.status == "queued",
    )
    pending = list((await db.execute(q)).scalars().all())

    sent = 0
    failed = 0
    for req in pending:
        if smtp_ready:
            result = await client.send_email(
                to_email=req.to_email,
                subject=req.subject,
                body_html=req.body_html or "",
                body_text=req.body_text or "",
            )
            if result.get("success"):
                req.status = "sent"
                req.sent_at = datetime.now(timezone.utc).isoformat()
                sent += 1
            elif result.get("blocked"):
                req.status = "failed"
                req.error_message = result.get("error", "Email provider not configured")
                req.retry_count += 1
                failed += 1
            else:
                req.status = "failed"
                req.error_message = result.get("error", "Send failed")
                req.retry_count += 1
                failed += 1
        else:
            req.status = "failed"
            req.error_message = (
                "No email provider configured for this organization "
                "(integration_providers.provider_key='smtp' and no env-legacy fallback available)"
            )
            req.retry_count += 1
            failed += 1

    await db.commit()
    return {"created": 0, "updated": sent + failed, "details": f"sent={sent}, failed={failed}, smtp_source={client.source}"}


# ── SMS ────────────────────────────────────────────────────────────────

async def list_sms_requests(db: AsyncSession, brand_id: uuid.UUID) -> list[SmsSendRequest]:
    q = select(SmsSendRequest).where(
        SmsSendRequest.brand_id == brand_id,
        SmsSendRequest.is_active.is_(True),
    ).order_by(SmsSendRequest.created_at.desc()).limit(200)
    return list((await db.execute(q)).scalars().all())


async def create_sms_send(db: AsyncSession, brand_id: uuid.UUID, data: dict[str, Any]) -> SmsSendRequest:
    brand_ctx = {"has_sms_api_key": bool(os.environ.get("SMS_API_KEY"))}
    validation = validate_sms_send(data, brand_ctx)

    req = SmsSendRequest(
        brand_id=brand_id,
        contact_id=data.get("contact_id"),
        to_phone=data["to_phone"],
        message_body=data["message_body"],
        sequence_step=data.get("sequence_step"),
        provider=data.get("provider", "twilio"),
        status="queued" if validation["valid"] else "failed",
        error_message=validation.get("error"),
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


async def execute_pending_sms(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    has_sms = bool(os.environ.get("SMS_API_KEY"))

    q = select(SmsSendRequest).where(
        SmsSendRequest.brand_id == brand_id,
        SmsSendRequest.is_active.is_(True),
        SmsSendRequest.status == "queued",
    )
    pending = list((await db.execute(q)).scalars().all())

    sent = 0
    failed = 0
    for req in pending:
        if has_sms:
            from packages.clients.external_clients import TwilioSmsClient
            client = TwilioSmsClient()
            result = await client.send_sms(
                to_phone=req.to_phone,
                message_body=req.message_body,
            )
            if result.get("success"):
                req.status = "sent"
                req.sent_at = datetime.now(timezone.utc).isoformat()
                req.external_message_id = result.get("message_sid")
                sent += 1
            elif result.get("blocked"):
                req.status = "failed"
                req.error_message = result.get("error", "SMS provider not configured")
                req.retry_count += 1
                failed += 1
            else:
                req.status = "failed"
                req.error_message = result.get("error", "Send failed")
                req.retry_count += 1
                failed += 1
        else:
            req.status = "failed"
            req.error_message = "No SMS provider configured"
            req.retry_count += 1
            failed += 1

    await db.commit()
    return {"created": 0, "updated": sent + failed, "details": f"sent={sent}, failed={failed}"}


# ── Messaging Blockers ────────────────────────────────────────────────

async def list_messaging_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list[MessagingBlocker]:
    q = select(MessagingBlocker).where(
        MessagingBlocker.brand_id == brand_id,
        MessagingBlocker.is_active.is_(True),
    ).order_by(MessagingBlocker.created_at.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_messaging_blockers(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(MessagingBlocker)
        .where(MessagingBlocker.brand_id == brand_id, MessagingBlocker.is_active.is_(True))
        .values(is_active=False)
    )

    contacts_q = select(CrmContact).where(CrmContact.brand_id == brand_id, CrmContact.is_active.is_(True))
    contacts_count = len(list((await db.execute(contacts_q)).scalars().all()))

    # SMTP presence is resolved DB-first via SmtpEmailClient.resolve (system-managed).
    # SMS / ESP / CRM keys remain as legacy env reads — to be migrated to DB in a later pass.
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.core import Brand
    org_id = (await db.execute(
        select(Brand.organization_id).where(Brand.id == brand_id)
    )).scalar_one_or_none()
    has_smtp = False
    if org_id:
        smtp_client = await SmtpEmailClient.resolve(db, org_id)
        has_smtp = smtp_client._is_configured()

    brand_ctx = {
        "has_smtp_config": has_smtp,
        "has_sms_api_key": bool(os.environ.get("SMS_API_KEY")),  # legacy — migrate next
        "has_esp_api_key": bool(os.environ.get("ESP_API_KEY")),  # legacy — migrate next
        "has_crm_credentials": bool(os.environ.get("CRM_API_KEY")),  # legacy — migrate next
        "contacts_count": contacts_count,
    }

    blockers = detect_messaging_blockers(brand_ctx)
    for b in blockers:
        db.add(MessagingBlocker(brand_id=brand_id, **b))

    await db.commit()
    return {"created": len(blockers), "updated": 0}
