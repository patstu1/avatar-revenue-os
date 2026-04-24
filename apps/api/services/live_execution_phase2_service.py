"""Service layer for Live Execution Phase 2 + Buffer Expansion."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.buffer_distribution import (
    BufferProfile,
    BufferPublishJob,
)
from packages.db.models.live_execution_phase2 import (
    AdReportingImport,
    BufferCapabilityCheck,
    BufferExecutionTruth,
    BufferRetryRecord,
    ExternalEventIngestion,
    PaymentConnectorSync,
    PlatformAnalyticsSync,
    SequenceTriggerAction,
    WebhookEvent,
)
from packages.scoring.live_execution_phase2_engine import (
    build_ingestion_summary,
    check_duplicate_submit,
    classify_buffer_truth_state,
    classify_webhook_source,
    compute_retry_backoff,
    detect_stale_jobs,
    determine_sequence_triggers,
    evaluate_analytics_sync_readiness,
    evaluate_buffer_profile_readiness,
    evaluate_payment_sync_readiness,
)


def _row_to_dict(row) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for c in row.__table__.columns:
        val = getattr(row, c.name)
        if isinstance(val, uuid.UUID):
            val = str(val)
        d[c.name] = val
    return d


# ── A. Webhook Events ──────────────────────────────────────────────────

async def ingest_webhook_event(
    db: AsyncSession, brand_id_opt: uuid.UUID | None, data: dict[str, Any],
) -> dict[str, Any]:
    idem_key = data.get("idempotency_key")
    if idem_key:
        q = select(WebhookEvent.idempotency_key).where(
            WebhookEvent.idempotency_key == idem_key,
        )
        existing = (await db.execute(q)).scalar_one_or_none()
        if existing:
            return {"rows_processed": 0, "status": "duplicate", "idempotency_key": idem_key}

    classification = classify_webhook_source(data.get("source", ""))
    evt = WebhookEvent(
        brand_id=brand_id_opt,
        source=classification["source"],
        source_category=classification["source_category"],
        event_type=data.get("event_type", "unknown"),
        external_event_id=data.get("external_event_id"),
        raw_payload=data.get("raw_payload"),
        idempotency_key=idem_key,
        processed=False,
    )
    db.add(evt)
    await db.flush()
    return {"rows_processed": 1, "status": "ingested"}


async def list_webhook_events(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(WebhookEvent)
        .where(WebhookEvent.brand_id == brand_id, WebhookEvent.is_active.is_(True))
        .order_by(WebhookEvent.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


# ── B. External Event Ingestions ───────────────────────────────────────

async def list_event_ingestions(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(ExternalEventIngestion)
        .where(ExternalEventIngestion.brand_id == brand_id, ExternalEventIngestion.is_active.is_(True))
        .order_by(ExternalEventIngestion.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def recompute_event_ingestions(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(
        delete(ExternalEventIngestion).where(ExternalEventIngestion.brand_id == brand_id)
    )

    q = select(
        WebhookEvent.source,
        WebhookEvent.source_category,
        func.count().label("total"),
        func.count().filter(WebhookEvent.processed.is_(True)).label("processed"),
    ).where(
        WebhookEvent.brand_id == brand_id,
        WebhookEvent.is_active.is_(True),
    ).group_by(WebhookEvent.source, WebhookEvent.source_category)

    agg_rows = (await db.execute(q)).all()
    created = 0
    for row in agg_rows:
        total = row.total
        processed = row.processed
        skipped = 0
        failed = total - processed - skipped
        if failed < 0:
            failed = 0
        summary = build_ingestion_summary(total, processed, skipped, failed)
        ing = ExternalEventIngestion(
            brand_id=brand_id,
            source=row.source,
            source_category=row.source_category,
            ingestion_mode="webhook",
            events_received=total,
            events_processed=processed,
            events_skipped=skipped,
            events_failed=failed,
            status=summary["status"],
        )
        db.add(ing)
        created += 1

    await db.flush()
    return {"rows_processed": created, "status": "completed"}


# ── C. Sequence Triggers ──────────────────────────────────────────────

async def list_sequence_triggers(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(SequenceTriggerAction)
        .where(SequenceTriggerAction.brand_id == brand_id, SequenceTriggerAction.is_active.is_(True))
        .order_by(SequenceTriggerAction.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def process_sequence_triggers(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    q = select(WebhookEvent).where(
        WebhookEvent.brand_id == brand_id,
        WebhookEvent.is_active.is_(True),
        WebhookEvent.processed.is_(False),
    )
    unprocessed = list((await db.execute(q)).scalars().all())
    created = 0
    for evt in unprocessed:
        triggers = determine_sequence_triggers(evt.event_type, evt.source_category)
        for t in triggers:
            action = SequenceTriggerAction(
                brand_id=brand_id,
                trigger_source=evt.source,
                trigger_event_type=evt.event_type,
                trigger_event_id=evt.id,
                action_type=t["action_type"],
                action_target=t.get("reason"),
                status="pending",
            )
            db.add(action)
            created += 1
        evt.processed = True

    await db.flush()
    return {"rows_processed": created, "status": "completed"}


# ── D. Payment Syncs ──────────────────────────────────────────────────

async def list_payment_syncs(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(PaymentConnectorSync)
        .where(PaymentConnectorSync.brand_id == brand_id, PaymentConnectorSync.is_active.is_(True))
        .order_by(PaymentConnectorSync.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def run_payment_sync(
    db: AsyncSession, brand_id: uuid.UUID, provider: str = "stripe",
) -> dict[str, Any]:
    api_key_present = bool(os.environ.get(f"{provider.upper()}_API_KEY", ""))
    readiness = evaluate_payment_sync_readiness(provider, api_key_present)

    row = PaymentConnectorSync(
        brand_id=brand_id,
        provider=provider,
        sync_mode="incremental",
        status="blocked",
        credential_status=readiness.get("credential_status", "not_configured"),
        error_message=readiness.get("operator_action") if not readiness.get("sync_ready") else None,
        details_json={"readiness": readiness},
    )

    if api_key_present:
        if provider == "stripe":
            from packages.clients.external_clients import StripePaymentClient
            client = StripePaymentClient()
            result = await client.fetch_recent_charges()
        elif provider == "shopify":
            from packages.clients.external_clients import ShopifyOrderClient
            client = ShopifyOrderClient()
            result = await client.fetch_recent_orders()
        else:
            result = {"success": False, "blocked": True, "error": f"Unsupported provider: {provider}", "data": {}}

        data = result.get("data", {})

        if result.get("success"):
            row.orders_imported = int(data.get("orders_imported", 0))
            row.revenue_imported = float(data.get("revenue_imported", 0.0))
            row.refunds_imported = int(data.get("refunds_imported", 0))
            row.status = "completed"
            row.credential_status = "configured"
            row.last_cursor = data.get("last_id")
            row.details_json = {"readiness": readiness, "sync_result": {
                "orders": row.orders_imported,
                "revenue": row.revenue_imported,
                "refunds": row.refunds_imported,
            }}

            revenue_events_created = await _create_revenue_events_from_sync(
                db, brand_id, provider, data
            )
            row.details_json["revenue_events_created"] = revenue_events_created
        elif result.get("blocked"):
            row.status = "blocked"
            row.error_message = result.get("error")
        else:
            row.status = "failed"
            row.error_message = result.get("error")
            row.details_json = {"readiness": readiness, "error_data": data}

    db.add(row)
    await db.flush()
    return {"rows_processed": 1, "status": row.status}


async def _create_revenue_events_from_sync(
    db: AsyncSession, brand_id: uuid.UUID, provider: str, data: dict,
) -> int:
    """Create CreatorRevenueEvent rows from payment sync data, deduped by external_id."""
    from packages.db.models.creator_revenue import CreatorRevenueEvent

    created = 0

    if provider == "stripe":
        for charge in data.get("charges", []):
            if not charge.get("paid"):
                continue
            ext_id = charge.get("id", "")
            existing = (await db.execute(
                select(CreatorRevenueEvent).where(
                    CreatorRevenueEvent.brand_id == brand_id,
                    CreatorRevenueEvent.metadata_json["stripe_charge_id"].astext == ext_id,
                )
            )).scalar_one_or_none()
            if existing:
                continue
            amount = float(charge.get("amount", 0)) / 100.0
            if amount <= 0:
                continue
            db.add(CreatorRevenueEvent(
                brand_id=brand_id,
                avenue_type="consulting" if "consulting" in str(charge.get("metadata", {})) else "ugc_services",
                event_type="stripe_charge_sync",
                revenue=amount,
                cost=0.0,
                profit=amount,
                client_name=charge.get("receipt_email") or charge.get("billing_details", {}).get("email", ""),
                description=f"Stripe charge {ext_id}: ${amount:.2f}",
                metadata_json={"stripe_charge_id": ext_id, "source": "payment_sync"},
            ))
            created += 1

    elif provider == "shopify":
        for order in data.get("orders", []):
            ext_id = str(order.get("id", ""))
            existing = (await db.execute(
                select(CreatorRevenueEvent).where(
                    CreatorRevenueEvent.brand_id == brand_id,
                    CreatorRevenueEvent.metadata_json["shopify_order_id"].astext == ext_id,
                )
            )).scalar_one_or_none()
            if existing:
                continue
            amount = float(order.get("total_price", 0))
            if order.get("financial_status") == "refunded":
                amount = -amount
            if amount == 0:
                continue
            event_type = "shopify_refund_sync" if amount < 0 else "shopify_order_sync"
            db.add(CreatorRevenueEvent(
                brand_id=brand_id,
                avenue_type="ecommerce",
                event_type=event_type,
                revenue=amount,
                cost=0.0,
                profit=amount,
                client_name=order.get("email", ""),
                description=f"Shopify order #{order.get('order_number', ext_id)}: ${abs(amount):.2f}",
                metadata_json={"shopify_order_id": ext_id, "source": "payment_sync"},
            ))
            created += 1

    if created:
        await db.flush()
    return created


# ── E. Analytics Syncs ────────────────────────────────────────────────

async def list_analytics_syncs(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(PlatformAnalyticsSync)
        .where(PlatformAnalyticsSync.brand_id == brand_id, PlatformAnalyticsSync.is_active.is_(True))
        .order_by(PlatformAnalyticsSync.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def run_analytics_sync(
    db: AsyncSession, brand_id: uuid.UUID, source: str = "buffer",
) -> dict[str, Any]:
    env_var = f"{source.upper()}_API_KEY"
    has_key = bool(os.environ.get(env_var))
    readiness = evaluate_analytics_sync_readiness(source, has_key)

    classification = classify_webhook_source(source)
    sync = PlatformAnalyticsSync(
        brand_id=brand_id,
        source=source,
        source_category=classification["source_category"],
        sync_mode="scheduled",
        metrics_imported=0,
        content_items_matched=0,
        attribution_refreshed=False,
        reconciliation_status="clean",
        credential_status=readiness["credential_status"],
        blocker_state=readiness.get("blocker_state"),
        operator_action=readiness.get("operator_action"),
    )
    db.add(sync)
    await db.flush()
    return {"rows_processed": 1, "status": "completed"}


# ── F. Ad Imports ─────────────────────────────────────────────────────

async def list_ad_imports(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(AdReportingImport)
        .where(AdReportingImport.brand_id == brand_id, AdReportingImport.is_active.is_(True))
        .order_by(AdReportingImport.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def run_ad_import(
    db: AsyncSession, brand_id: uuid.UUID, platform: str = "meta_ads",
) -> dict[str, Any]:
    from packages.clients.external_clients import GoogleAdsClient, MetaAdsClient, TikTokAdsClient

    clients = {
        "meta_ads": MetaAdsClient,
        "google_ads": GoogleAdsClient,
        "tiktok_ads": TikTokAdsClient,
    }

    client_cls = clients.get(platform)
    if not client_cls:
        row = AdReportingImport(
            brand_id=brand_id, ad_platform=platform,
            reconciliation_status="unreconciled",
            error_message=f"Unsupported ad platform: {platform}",
            credential_status="not_configured",
            blocker_state="unsupported_platform",
            operator_action=f"Platform '{platform}' is not supported. Use: meta_ads, google_ads, tiktok_ads.",
        )
        db.add(row)
        await db.flush()
        return {"rows_processed": 0, "status": "failed"}

    client = client_cls()
    result = await client.fetch_campaign_report() if hasattr(client, 'fetch_campaign_report') else await client.fetch_campaign_insights()

    data = result.get("data", {})

    row = AdReportingImport(
        brand_id=brand_id,
        ad_platform=platform,
        report_type="campaign_summary",
        campaigns_imported=len(data.get("campaigns", [])) if isinstance(data.get("campaigns"), list) else int(data.get("campaigns_imported", 0)),
        spend_imported=float(data.get("spend", 0)),
        impressions_imported=int(data.get("impressions", 0)),
        clicks_imported=int(data.get("clicks", 0)),
        conversions_imported=int(data.get("conversions", 0)),
        revenue_attributed=float(data.get("revenue_attributed", 0)),
        source_classification="ads",
        reconciliation_status="clean" if result.get("success") else "unreconciled",
        credential_status="configured" if result.get("success") else ("not_configured" if result.get("blocked") else "error"),
        blocker_state="missing_credentials" if result.get("blocked") else None,
        operator_action=result.get("error") if not result.get("success") else None,
        error_message=result.get("error"),
        details_json={"raw_response": data},
    )
    db.add(row)
    await db.flush()
    return {"rows_processed": 1, "status": "completed" if result.get("success") else "blocked" if result.get("blocked") else "failed"}


# ── G. Buffer Execution Truth ─────────────────────────────────────────

async def list_buffer_execution_truth(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(BufferExecutionTruth)
        .where(BufferExecutionTruth.brand_id == brand_id, BufferExecutionTruth.is_active.is_(True))
        .order_by(BufferExecutionTruth.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def recompute_buffer_execution_truth(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(
        delete(BufferExecutionTruth).where(BufferExecutionTruth.brand_id == brand_id)
    )

    q = select(BufferPublishJob).where(
        BufferPublishJob.brand_id == brand_id,
        BufferPublishJob.is_active.is_(True),
    )
    jobs = list((await db.execute(q)).scalars().all())

    existing_keys: set[str] = set()
    for j in jobs:
        if j.content_item_id and j.platform:
            existing_keys.add(f"{j.content_item_id}:{j.platform.value if hasattr(j.platform, 'value') else j.platform}")

    now = datetime.now(timezone.utc)
    created = 0
    for job in jobs:
        hours = 0.0
        if job.created_at:
            delta = now - job.created_at.replace(tzinfo=timezone.utc) if job.created_at.tzinfo is None else now - job.created_at
            hours = delta.total_seconds() / 3600.0

        truth = classify_buffer_truth_state(
            job_status=job.status or "unknown",
            buffer_post_id=job.buffer_post_id,
            retry_count=job.retry_count or 0,
            hours_since_submit=hours,
        )

        platform_str = job.platform.value if hasattr(job.platform, "value") else str(job.platform)
        is_dup = False
        if job.content_item_id:
            is_dup = check_duplicate_submit(
                str(job.content_item_id), platform_str, existing_keys,
            )

        stale = detect_stale_jobs(hours, truth["truth_state"])

        row = BufferExecutionTruth(
            brand_id=brand_id,
            buffer_publish_job_id=job.id,
            content_item_id=job.content_item_id,
            truth_state=truth["truth_state"],
            is_duplicate=is_dup,
            is_stale=stale["is_stale"],
            stale_since=str(now) if stale["is_stale"] else None,
            conflict_detected=is_dup,
            conflict_description="duplicate_content_platform_pair" if is_dup else None,
            operator_action=truth.get("operator_action") or stale.get("operator_action"),
        )
        db.add(row)
        created += 1

    await db.flush()
    return {"rows_processed": created, "status": "completed"}


# ── H. Buffer Retries ─────────────────────────────────────────────────

async def list_buffer_retries(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(BufferRetryRecord)
        .where(BufferRetryRecord.brand_id == brand_id, BufferRetryRecord.is_active.is_(True))
        .order_by(BufferRetryRecord.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def recompute_buffer_retries(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(
        delete(BufferRetryRecord).where(BufferRetryRecord.brand_id == brand_id)
    )

    q = select(BufferPublishJob).where(
        BufferPublishJob.brand_id == brand_id,
        BufferPublishJob.is_active.is_(True),
        BufferPublishJob.status.in_(["failed", "failed_in_buffer", "degraded"]),
    )
    failed_jobs = list((await db.execute(q)).scalars().all())

    created = 0
    for job in failed_jobs:
        attempt = (job.retry_count or 0) + 1
        backoff = compute_retry_backoff(attempt)
        rec = BufferRetryRecord(
            brand_id=brand_id,
            buffer_publish_job_id=job.id,
            attempt_number=attempt,
            retry_reason=job.error_message or "unknown_failure",
            backoff_seconds=backoff["backoff_seconds"],
            outcome=backoff["next_action"],
            escalated=backoff["should_escalate"],
            error_message=job.error_message,
        )
        db.add(rec)
        created += 1

    await db.flush()
    return {"rows_processed": created, "status": "completed"}


# ── I. Buffer Capabilities ────────────────────────────────────────────

async def list_buffer_capabilities(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(BufferCapabilityCheck)
        .where(BufferCapabilityCheck.brand_id == brand_id, BufferCapabilityCheck.is_active.is_(True))
        .order_by(BufferCapabilityCheck.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def recompute_buffer_capabilities(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(
        delete(BufferCapabilityCheck).where(BufferCapabilityCheck.brand_id == brand_id)
    )

    q = select(BufferProfile).where(
        BufferProfile.brand_id == brand_id,
        BufferProfile.is_active.is_(True),
    )
    profiles = list((await db.execute(q)).scalars().all())

    created = 0
    for prof in profiles:
        platform_str = prof.platform.value if hasattr(prof.platform, "value") else str(prof.platform)
        readiness = evaluate_buffer_profile_readiness(
            credential_status=prof.credential_status or "not_connected",
            buffer_profile_id=prof.buffer_profile_id,
            platform=platform_str,
            is_active=prof.is_active,
        )
        check = BufferCapabilityCheck(
            brand_id=brand_id,
            buffer_profile_id_fk=prof.id,
            profile_ready=readiness["profile_ready"],
            credential_valid=readiness["credential_valid"],
            missing_profile_mapping=readiness["missing_profile_mapping"],
            inactive_profile=readiness["inactive_profile"],
            platform_supported=readiness["platform_supported"],
            unsupported_modes=readiness["unsupported_modes"],
            blocker_summary=readiness["blocker_summary"],
            operator_action=readiness["operator_action"],
        )
        db.add(check)
        created += 1

    await db.flush()
    return {"rows_processed": created, "status": "completed"}
