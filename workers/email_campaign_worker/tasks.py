"""Email Campaign Worker — send nurture sequences, weekly digests, and monetization emails."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, update

from workers.base_task import TrackedTask

from packages.db.session import async_session_factory, run_async
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _send_pending_emails():
    """Process pending email send requests queued in the email_send_requests table."""
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.live_execution import EmailSendRequest

    client = SmtpEmailClient()
    if not client._is_configured():
        return {"sent": 0, "failed": 0, "reason": "SMTP not configured — set SMTP_HOST and SMTP_FROM_EMAIL env vars"}

    total_sent = 0
    total_failed = 0

    async with async_session_factory() as db:
        pending = (await db.execute(
            select(EmailSendRequest).where(
                EmailSendRequest.status == "queued",
                EmailSendRequest.is_active.is_(True),
                EmailSendRequest.retry_count < 3,
            ).order_by(EmailSendRequest.created_at).limit(100)
        )).scalars().all()

        for req in pending:
            try:
                result = await client.send_email(
                    to_email=req.to_email,
                    subject=req.subject,
                    body_html=req.body_html or "",
                    body_text=req.body_text or "",
                )
                if result.get("success"):
                    req.status = "sent"
                    req.sent_at = datetime.now(timezone.utc).isoformat()
                    req.error_message = None
                    total_sent += 1
                    logger.info("email sent to %s (request %s)", req.to_email, req.id)
                else:
                    req.retry_count += 1
                    req.error_message = result.get("error", "Unknown SMTP error")
                    if req.retry_count >= 3:
                        req.status = "failed"
                    total_failed += 1
                    logger.warning("email failed for %s: %s", req.to_email, req.error_message)
            except Exception as e:
                req.retry_count += 1
                req.error_message = str(e)
                if req.retry_count >= 3:
                    req.status = "failed"
                total_failed += 1
                logger.exception("email send exception for request %s", req.id)

        await db.commit()

    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id).where(Brand.is_active.is_(True)))).scalars().all())

    for bid in brands:
        try:
            async with async_session_factory() as db:
                from apps.api.services.lead_magnet_service import identify_lead_magnet_opportunities, generate_lead_magnet
                opportunities = await identify_lead_magnet_opportunities(db, bid)
                for opp in opportunities[:1]:
                    result = await generate_lead_magnet(db, bid, opp["topic"], opp["magnet_type"])
                    if result.get("success"):
                        logger.info("lead magnet created: brand=%s topic=%s", bid, opp["topic"])
                await db.commit()
        except Exception:
            logger.exception("lead magnet generation failed for brand %s", bid)

    return {"brands_processed": len(brands), "total_sent": total_sent, "total_failed": total_failed}


@shared_task(name="workers.email_campaign_worker.tasks.process_email_campaigns", base=TrackedTask)
def process_email_campaigns():
    return run_async(_send_pending_emails())
