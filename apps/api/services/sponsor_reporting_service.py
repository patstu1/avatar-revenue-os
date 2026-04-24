"""Sponsor reporting (Batch 13).

Closes Fu:P → Fu:Y for sponsor_deals. Compiles periodic performance
reports by aggregating SponsorPlacement.metrics_json for a window,
then sends the report to the sponsor contact.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.sponsor_campaigns import (
    SponsorCampaign,
    SponsorPlacement,
    SponsorReport,
)

logger = structlog.get_logger()


def _aggregate_metrics(placements: list[SponsorPlacement]) -> dict:
    """Roll up placement-level metrics into campaign-period totals."""
    totals: dict = {
        "placements_scheduled": 0,
        "placements_delivered": 0,
        "placements_missed": 0,
        "placements_make_good": 0,
        "impressions": 0,
        "clicks": 0,
        "conversions": 0,
        "engagement": 0,
    }
    for p in placements:
        totals["placements_scheduled"] += 1
        if p.status == "delivered":
            totals["placements_delivered"] += 1
        elif p.status == "missed":
            totals["placements_missed"] += 1
        if p.make_good_of_placement_id is not None:
            totals["placements_make_good"] += 1
        m = p.metrics_json or {}
        for key in ("impressions", "clicks", "conversions", "engagement"):
            v = m.get(key, 0)
            try:
                totals[key] += int(v)
            except (TypeError, ValueError):
                continue
    return totals


async def compile_report(
    db: AsyncSession,
    *,
    campaign: SponsorCampaign,
    period_start: datetime,
    period_end: datetime,
    report_type: str = "monthly",
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> SponsorReport:
    """Compile placement metrics for [period_start, period_end] into
    a SponsorReport row. Status=draft; a separate ``send_report`` call
    delivers it.
    """
    if period_end <= period_start:
        raise ValueError("period_end must be after period_start")

    # Placements that overlap the window (scheduled_at or delivered_at
    # within the window is good enough for the proof of concept).
    q = select(SponsorPlacement).where(
        SponsorPlacement.campaign_id == campaign.id,
        SponsorPlacement.is_active.is_(True),
        or_(
            and_(SponsorPlacement.scheduled_at >= period_start, SponsorPlacement.scheduled_at <= period_end),
            and_(SponsorPlacement.delivered_at >= period_start, SponsorPlacement.delivered_at <= period_end),
        ),
    )
    placements = list((await db.execute(q)).scalars().all())
    metrics = _aggregate_metrics(placements)

    now = datetime.now(timezone.utc)
    report = SponsorReport(
        campaign_id=campaign.id,
        org_id=campaign.org_id,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        status="draft",
        compiled_at=now,
        metrics_json=metrics,
        is_active=True,
    )
    db.add(report)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="sponsor.report.compiled",
        summary=(
            f"Report compiled: {report_type} "
            f"[{period_start.date()} → {period_end.date()}] "
            f"placements={metrics['placements_scheduled']} "
            f"impressions={metrics['impressions']}"
        ),
        org_id=campaign.org_id,
        entity_type="sponsor_report",
        entity_id=report.id,
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "report_id": str(report.id),
            "campaign_id": str(campaign.id),
            "report_type": report_type,
            "metrics": metrics,
        },
    )
    return report


async def send_report(
    db: AsyncSession,
    *,
    report: SponsorReport,
    recipient_email: str,
    actor_type: str = "operator",
    actor_id: str | None = None,
) -> dict:
    """Mark the report sent + attempt SMTP delivery. Graceful failure."""
    if report.status == "sent":
        return {
            "triggered": False,
            "reason": "already_sent",
            "report_id": str(report.id),
        }

    report.recipient_email = recipient_email[:255]
    report.sent_at = datetime.now(timezone.utc)
    report.status = "sent"
    await db.flush()

    send_result = {"success": False, "error": "no_smtp_configured"}
    try:
        from packages.clients.external_clients import SmtpEmailClient

        smtp = await SmtpEmailClient.from_db(db, report.org_id)
        if smtp is not None:
            m = report.metrics_json or {}
            subject = f"Campaign report — {report.period_start.date()} → {report.period_end.date()}"
            body = (
                f"Campaign report\n"
                f"Period: {report.period_start.date()} → {report.period_end.date()}\n"
                f"Type:   {report.report_type}\n\n"
                f"Placements scheduled: {m.get('placements_scheduled', 0)}\n"
                f"Placements delivered: {m.get('placements_delivered', 0)}\n"
                f"Placements missed:    {m.get('placements_missed', 0)}\n"
                f"Make-goods:           {m.get('placements_make_good', 0)}\n\n"
                f"Impressions: {m.get('impressions', 0):,}\n"
                f"Clicks:      {m.get('clicks', 0):,}\n"
                f"Conversions: {m.get('conversions', 0):,}\n"
            )
            send_result = await smtp.send_email(
                to_email=recipient_email,
                subject=subject,
                body_text=body,
                body_html=f"<pre>{body}</pre>",
            )
    except Exception as smtp_exc:
        send_result = {"success": False, "error": str(smtp_exc)[:200]}

    await emit_event(
        db,
        domain="fulfillment",
        event_type="sponsor.report.sent",
        summary=f"Sponsor report sent to {recipient_email}",
        org_id=report.org_id,
        entity_type="sponsor_report",
        entity_id=report.id,
        actor_type=actor_type,
        actor_id=actor_id,
        severity="info" if send_result.get("success") else "warning",
        details={
            "report_id": str(report.id),
            "campaign_id": str(report.campaign_id),
            "recipient_email": recipient_email,
            "send_success": bool(send_result.get("success")),
            "send_error": send_result.get("error"),
        },
    )
    return {
        "triggered": True,
        "report_id": str(report.id),
        "status": "sent",
        "sent_at": report.sent_at.isoformat(),
        "send_success": bool(send_result.get("success")),
        "send_error": send_result.get("error"),
    }
