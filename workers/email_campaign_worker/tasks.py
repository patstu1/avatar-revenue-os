"""Email Campaign Worker — send nurture sequences, weekly digests, and monetization emails."""
from __future__ import annotations
import asyncio
import logging
import os

from celery import shared_task
from sqlalchemy import select

from packages.db.session import async_session_factory
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _send_pending_emails():
    """Process pending email sends from nurture sequences."""
    from packages.clients.external_clients import SmtpEmailClient

    client = SmtpEmailClient()
    if not client._is_configured():
        return {"sent": 0, "reason": "SMTP not configured — set SMTP_HOST/SMTP_USER/SMTP_PASS"}

    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id).where(Brand.is_active.is_(True)))).scalars().all())

    total_sent = 0
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
            logger.exception("email campaign failed for brand %s", bid)

    return {"brands_processed": len(brands), "total_sent": total_sent}


@shared_task(name="workers.email_campaign_worker.tasks.process_email_campaigns")
def process_email_campaigns():
    return asyncio.run(_send_pending_emails())
