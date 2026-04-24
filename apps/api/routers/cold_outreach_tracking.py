"""Click-redirector for cold-outreach email URLs.

Logs every click in `cold_outreach_clicks` keyed by sponsor_target_id so
the operator can see exactly which leads engaged (per-lead click
attribution, not just aggregate traffic counts).

URL shape in cold emails:
    https://app.nvironments.com/r/<target_id>?c=<campaign>

302 redirects to proofhook.com with UTMs preserved, which means analytics
on proofhook.com still see the traffic and we get per-lead signal.
"""

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from apps.api.deps import DBSession

logger = structlog.get_logger()
router = APIRouter()

DEFAULT_CAMPAIGN = "b2b_apr26"
REDIRECT_BASE = "https://proofhook.com/"


@router.get("/r/{target_id}")
async def click_redirector(target_id: str, request: Request, db: DBSession):
    """Log a cold-email click and 302 to proofhook.com with UTMs preserved."""
    ua = (request.headers.get("user-agent") or "")[:500]
    ip = request.client.host if request.client else None
    ref = (request.headers.get("referer") or "")[:500]
    campaign = (request.query_params.get("c") or DEFAULT_CAMPAIGN)[:64]

    # Insert click (best-effort — if target_id is malformed we still redirect)
    try:
        await db.execute(
            text(
                "INSERT INTO cold_outreach_clicks "
                "(target_id, campaign, user_agent, ip_address, referer) "
                "VALUES (CAST(:t AS uuid), :c, :ua, :ip, :ref)"
            ),
            {"t": target_id, "c": campaign, "ua": ua, "ip": ip, "ref": ref},
        )
        await db.commit()
        logger.info("click.logged", target_id=target_id, campaign=campaign, ip=ip)
        # Phase 3: emit to analytics_events for dashboard truth.
        try:
            from packages.clients.analytics_emitter import emit_analytics_event
            from sqlalchemy import text as _atxt

            brand_row = (
                await db.execute(
                    _atxt("SELECT brand_id FROM sponsor_targets WHERE id = CAST(:t AS uuid)"), {"t": target_id}
                )
            ).first()
            if brand_row and brand_row[0]:
                await emit_analytics_event(
                    db,
                    brand_id=brand_row[0],
                    source="cold_outreach",
                    event_type="outreach.click",
                    metric_value=1.0,
                    truth_level="verified",
                    raw_json={
                        "target_id": str(target_id),
                        "campaign": campaign,
                        "ip": ip,
                        "user_agent": ua[:200],
                    },
                )
                await db.commit()
        except Exception as _aexc:
            logger.warning("analytics_emit_failed", error=str(_aexc)[:200])
    except Exception as exc:
        # Never block the redirect on a logging failure
        logger.warning("click.log_failed", target_id=target_id, error=str(exc))

    utm = f"?utm_source=cold_email&utm_medium=email&utm_campaign={campaign}&utm_content={target_id}"
    return RedirectResponse(url=REDIRECT_BASE + utm, status_code=302)
