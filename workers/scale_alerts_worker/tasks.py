"""Scale alerts recurring workers: alert, candidate, blocker, readiness, notification recompute."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from workers.celery_app import app
from workers.base_task import TrackedTask
from packages.db.session import async_session_factory, get_sync_engine, run_async
from packages.db.models.core import Brand
from packages.db.models.scale_alerts import NotificationDelivery
from packages.notifications.adapters import EmailAdapter, NotificationPayload, SlackWebhookAdapter, SMSAdapter

logger = structlog.get_logger()

MAX_DELIVERY_ATTEMPTS = 5


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@app.task(base=TrackedTask, bind=True, name="workers.scale_alerts_worker.tasks.recompute_all_alerts")
def recompute_all_alerts(self) -> dict:
    """Recompute scale alerts for all brands (async service)."""
    from apps.api.services import scale_alerts_service as sas

    async def _run():
        total = {"brands_processed": 0, "alerts_created": 0, "errors": []}
        async with async_session_factory() as db:
            r = await db.execute(select(Brand.id))
            ids = [row[0] for row in r.all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await sas.recompute_alerts(db, bid)
                    await db.commit()
                    total["alerts_created"] += int(res.get("alerts_created", 0))
                    total["brands_processed"] += 1
            except Exception as e:
                logger.exception("recompute_alerts failed for brand %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.scale_alerts_worker.tasks.recompute_all_launch_candidates")
def recompute_all_launch_candidates(self) -> dict:
    from apps.api.services import scale_alerts_service as sas

    async def _run():
        total = {"brands_processed": 0, "candidates_created": 0, "errors": []}
        async with async_session_factory() as db:
            r = await db.execute(select(Brand.id))
            ids = [row[0] for row in r.all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await sas.recompute_launch_candidates(db, bid)
                    await db.commit()
                    total["candidates_created"] += int(res.get("candidates_created", 0))
                    total["brands_processed"] += 1
            except Exception as e:
                logger.exception("recompute_launch_candidates failed for brand %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.scale_alerts_worker.tasks.recompute_all_blockers")
def recompute_all_blockers(self) -> dict:
    from apps.api.services import scale_alerts_service as sas

    async def _run():
        total = {"brands_processed": 0, "blockers_found": 0, "errors": []}
        async with async_session_factory() as db:
            r = await db.execute(select(Brand.id))
            ids = [row[0] for row in r.all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await sas.recompute_scale_blockers(db, bid)
                    await db.commit()
                    total["blockers_found"] += int(res.get("blockers_found", 0))
                    total["brands_processed"] += 1
            except Exception as e:
                logger.exception("recompute_scale_blockers failed for brand %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.scale_alerts_worker.tasks.recompute_all_readiness")
def recompute_all_readiness(self) -> dict:
    from apps.api.services import scale_alerts_service as sas

    async def _run():
        total = {"brands_processed": 0, "errors": []}
        async with async_session_factory() as db:
            r = await db.execute(select(Brand.id))
            ids = [row[0] for row in r.all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    await sas.recompute_launch_readiness(db, bid)
                    await db.commit()
                    total["brands_processed"] += 1
            except Exception as e:
                logger.exception("recompute_launch_readiness failed for brand %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return run_async(_run())


def _adapters():
    email = EmailAdapter(
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_pass=os.getenv("SMTP_PASS", ""),
    )
    slack = SlackWebhookAdapter(webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""))
    sms = SMSAdapter(api_key=os.getenv("SMS_API_KEY", ""))
    return {"email": email, "slack": slack, "sms": sms}


@app.task(base=TrackedTask, bind=True, name="workers.scale_alerts_worker.tasks.process_notification_deliveries")
def process_notification_deliveries(self) -> dict:
    """Attempt pending notification deliveries with retry and adapter calls."""
    engine = get_sync_engine()
    adapters = _adapters()
    processed = 0
    delivered = 0
    failed = 0
    with Session(engine) as db:
        pending = db.query(NotificationDelivery).filter(NotificationDelivery.status == "pending").limit(50).all()
        for nd in pending:
            processed += 1
            if nd.channel == "in_app":
                nd.status = "delivered"
                nd.delivered_at = datetime.now(timezone.utc).isoformat()
                delivered += 1
                continue

            p = nd.payload or {}
            payload = NotificationPayload(
                title=p.get("title", ""),
                summary=p.get("summary", ""),
                urgency=float(p.get("urgency", 0)),
                alert_type=p.get("alert_type", "unknown"),
                brand_id=str(nd.brand_id),
                alert_id=str(nd.alert_id) if nd.alert_id else None,
                detail_url=p.get("detail_url"),
            )
            recipient = nd.recipient or os.getenv("OPERATOR_NOTIFY_EMAIL", "operator@localhost")
            adapter = adapters.get(nd.channel)
            if not adapter:
                nd.attempts = (nd.attempts or 0) + 1
                nd.last_error = f"Unknown channel {nd.channel}"
                if nd.attempts >= MAX_DELIVERY_ATTEMPTS:
                    nd.status = "failed"
                    failed += 1
                continue

            nd.attempts = (nd.attempts or 0) + 1
            ok, err = run_async(adapter.send(payload, recipient))
            if ok:
                nd.status = "delivered"
                nd.delivered_at = datetime.now(timezone.utc).isoformat()
                nd.last_error = None
                delivered += 1
                logger.info("notification.delivered", channel=nd.channel, alert_id=str(nd.alert_id), brand_id=str(nd.brand_id))
            else:
                nd.last_error = err
                if nd.attempts >= MAX_DELIVERY_ATTEMPTS:
                    nd.status = "failed"
                    failed += 1
                    logger.error("notification.terminal_failure", channel=nd.channel, alert_id=str(nd.alert_id), brand_id=str(nd.brand_id), attempts=nd.attempts, last_error=err)
                else:
                    nd.status = "pending"
                    logger.warning("notification.retry_pending", channel=nd.channel, alert_id=str(nd.alert_id), attempts=nd.attempts, last_error=err)
        db.commit()
    return {"processed": processed, "delivered": delivered, "failed_terminal": failed}
