"""Fleet manager worker — recompute fleet status, generate expansion recommendations with
specific platform + niche suggestions, persist FleetStatusReport, create operator alerts."""
from __future__ import annotations

import logging
import uuid
from collections import Counter

from workers.celery_app import app
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.fleet_manager_worker.tasks.recompute_fleet_status")
def recompute_fleet_status(self) -> dict:
    """Count accounts by state, identify best expansion targets, persist reports, notify operator."""
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from packages.db.session import get_sync_engine
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.core import Brand, Organization
    from packages.db.enums import HealthStatus
    from packages.scoring.warmup_engine import determine_warmup_phase
    from packages.scoring.niche_research_engine import rank_niches, NICHE_DATABASE
    from packages.db.models.autonomous_farm import FleetStatusReport, NicheScore
    from packages.db.models.publishing import PerformanceMetric

    engine = get_sync_engine()
    fleet_summary: dict[str, int] = {"warming": 0, "scaling": 0, "plateaued": 0, "retired": 0, "suspended": 0}
    expansion_recommendations: list[dict] = []
    brands_processed = 0
    total_revenue_30d = 0.0

    with Session(engine) as session:
        brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()

        for brand in brands:
            try:
                accounts = session.execute(
                    select(CreatorAccount).where(CreatorAccount.brand_id == brand.id, CreatorAccount.is_active.is_(True))
                ).scalars().all()

                plateaued_accounts = 0
                active_platforms = Counter()
                active_niches = Counter()

                for account in accounts:
                    plat = getattr(account.platform, 'value', str(account.platform)) if account.platform else "unknown"
                    niche = account.niche_focus or brand.niche or "general"
                    active_platforms[plat] += 1
                    active_niches[niche] += 1

                    if account.account_health == HealthStatus.SUSPENDED:
                        fleet_summary["suspended"] += 1
                        continue

                    phase = determine_warmup_phase(account.created_at)
                    phase_name = phase["phase"]

                    if phase_name in ("seed", "trickle", "build"):
                        fleet_summary["warming"] += 1
                    elif phase_name == "scale":
                        drs = float(account.diminishing_returns_score or 0)
                        if drs > 0.7:
                            fleet_summary["plateaued"] += 1
                            plateaued_accounts += 1
                        else:
                            fleet_summary["scaling"] += 1
                    else:
                        fleet_summary["scaling"] += 1

                from datetime import datetime, timezone, timedelta
                rev_30d = session.execute(
                    select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0))
                    .where(PerformanceMetric.brand_id == brand.id, PerformanceMetric.measured_at >= datetime.now(timezone.utc) - timedelta(days=30))
                ).scalar() or 0.0
                total_revenue_30d += float(rev_30d)

                if plateaued_accounts > 0 and len(accounts) > 0 and plateaued_accounts / len(accounts) >= 0.3:
                    top_niches = rank_niches(top_n=10)

                    covered_combos = set()
                    for a in accounts:
                        p = getattr(a.platform, 'value', str(a.platform)) if a.platform else ""
                        n = a.niche_focus or brand.niche or ""
                        covered_combos.add(f"{p}:{n}")

                    best_expansion = None
                    for scored in top_niches:
                        combo = f"{scored['platform']}:{scored['niche']}"
                        same_plat_niche = active_platforms.get(scored["platform"], 0)
                        if combo not in covered_combos or same_plat_niche < 2:
                            best_expansion = scored
                            break

                    if not best_expansion and top_niches:
                        best_expansion = top_niches[0]

                    rec = {
                        "brand_id": str(brand.id),
                        "brand_name": brand.name,
                        "plateaued_count": plateaued_accounts,
                        "total_accounts": len(accounts),
                        "recommended_platform": best_expansion["platform"] if best_expansion else "tiktok",
                        "recommended_niche": best_expansion["niche"] if best_expansion else brand.niche,
                        "niche_score": best_expansion["composite_score"] if best_expansion else 0,
                        "reason": f"{plateaued_accounts}/{len(accounts)} accounts plateaued. Best opportunity: {best_expansion['niche']} on {best_expansion['platform']} (score {best_expansion['composite_score']:.2f})" if best_expansion else "Fleet saturation detected",
                        "suggested_username": f"@{(best_expansion['niche'] if best_expansion else 'new').replace('_', '')}_{uuid.uuid4().hex[:4]}",
                    }
                    expansion_recommendations.append(rec)

                    try:
                        from packages.db.models.scale_alerts import OperatorAlert
                        session.add(OperatorAlert(
                            brand_id=brand.id,
                            alert_type="expansion_recommendation",
                            severity="high",
                            title=f"Add {rec['recommended_platform'].upper()} account in {rec['recommended_niche'].replace('_', ' ')}",
                            description=rec["reason"],
                            operator_action_needed=f"Create a new {rec['recommended_platform']} account for {rec['recommended_niche']} niche. Suggested username: {rec['suggested_username']}",
                        ))
                    except Exception:
                        logger.warning("Could not create operator alert for expansion rec")

                brands_processed += 1
            except Exception:
                logger.exception("Error computing fleet status for brand %s", brand.id)

        total_accounts = sum(fleet_summary.values())
        try:
            orgs = session.execute(select(Organization.id).limit(1)).scalars().all()
            if orgs:
                session.add(FleetStatusReport(
                    organization_id=orgs[0],
                    total_accounts=total_accounts,
                    accounts_warming=fleet_summary["warming"],
                    accounts_scaling=fleet_summary["scaling"],
                    accounts_plateaued=fleet_summary["plateaued"],
                    accounts_suspended=fleet_summary["suspended"],
                    accounts_retired=fleet_summary["retired"],
                    total_posts_today=0,
                    total_revenue_30d=total_revenue_30d,
                    expansion_recommended=len(expansion_recommendations) > 0,
                    expansion_details={"recommendations": expansion_recommendations} if expansion_recommendations else {},
                ))
        except Exception:
            logger.warning("Could not persist FleetStatusReport")

        session.commit()

    for rec in expansion_recommendations:
        logger.info(
            "EXPANSION RECOMMENDED: brand=%s platform=%s niche=%s score=%.2f reason=%s",
            rec["brand_name"], rec["recommended_platform"], rec["recommended_niche"],
            rec["niche_score"], rec["reason"],
        )

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "fleet_summary": fleet_summary,
        "total_accounts": total_accounts,
        "total_revenue_30d": round(total_revenue_30d, 2),
        "expansion_recommendations": expansion_recommendations,
    }


# ── OAuth Token Auto-Refresh ─────────────────────────────────────────


@app.task(base=TrackedTask, bind=True, name="workers.fleet_manager_worker.tasks.refresh_oauth_tokens")
def refresh_oauth_tokens(self) -> dict:
    """Check all creator accounts for expiring OAuth tokens and refresh proactively.

    Runs hourly. For each account with a token expiring within 24 hours:
    - If refresh_token exists: attempt refresh via platform OAuth endpoint
    - If refresh fails or no refresh_token: mark credential_status='expired', flag for operator
    - Block publishing for accounts with expired tokens
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from packages.db.session import get_sync_engine
    from packages.db.models.accounts import CreatorAccount
    from packages.db.enums import HealthStatus
    from datetime import datetime, timedelta, timezone
    import httpx

    engine = get_sync_engine()
    refreshed = 0
    expired_flagged = 0
    checked = 0

    now = datetime.now(timezone.utc)
    expiry_threshold = now + timedelta(hours=24)

    with Session(engine) as session:
        # Find accounts with tokens expiring within 24 hours
        expiring = session.execute(
            select(CreatorAccount).where(
                CreatorAccount.is_active.is_(True),
                CreatorAccount.platform_token_expires_at.isnot(None),
                CreatorAccount.platform_token_expires_at <= expiry_threshold,
                CreatorAccount.credential_status != "expired",
            )
        ).scalars().all()

        for acct in expiring:
            checked += 1
            platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)

            if not acct.platform_refresh_token:
                # No refresh token available — mark expired and block publishing
                acct.credential_status = "expired"
                acct.account_health = HealthStatus.DEGRADED
                expired_flagged += 1
                logger.warning("oauth.no_refresh_token",
                               account_id=str(acct.id), platform=platform,
                               username=acct.platform_username)
                continue

            # Attempt token refresh
            try:
                new_token, new_expiry = _refresh_platform_token(
                    platform, acct.platform_refresh_token, session, acct
                )
                if new_token:
                    acct.platform_access_token = new_token
                    acct.platform_token_expires_at = new_expiry
                    acct.credential_status = "connected"
                    acct.last_synced_at = now
                    refreshed += 1
                    logger.info("oauth.token_refreshed",
                                account_id=str(acct.id), platform=platform,
                                new_expiry=str(new_expiry))
                else:
                    # Refresh failed
                    acct.credential_status = "expired"
                    acct.account_health = HealthStatus.DEGRADED
                    expired_flagged += 1
                    logger.warning("oauth.refresh_failed",
                                   account_id=str(acct.id), platform=platform)

            except Exception as e:
                acct.credential_status = "expired"
                acct.account_health = HealthStatus.DEGRADED
                expired_flagged += 1
                logger.error("oauth.refresh_error",
                             account_id=str(acct.id), platform=platform, error=str(e))

        session.commit()

    return {
        "status": "completed",
        "checked": checked,
        "refreshed": refreshed,
        "expired_flagged": expired_flagged,
    }


def _refresh_platform_token(platform: str, refresh_token: str, session, acct) -> tuple:
    """Attempt to refresh OAuth token for a platform. Returns (new_token, new_expiry) or (None, None)."""
    import httpx
    import os
    from datetime import datetime, timedelta, timezone

    try:
        if platform == "youtube":
            resp = httpx.post("https://oauth2.googleapis.com/token", data={
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                expires_in = data.get("expires_in", 3600)
                return data["access_token"], datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        elif platform == "tiktok":
            resp = httpx.post("https://open.tiktokapis.com/v2/oauth/token/", data={
                "client_key": os.environ.get("TIKTOK_CLIENT_KEY", ""),
                "client_secret": os.environ.get("TIKTOK_CLIENT_SECRET", ""),
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("data", {}).get("access_token") or data.get("access_token")
                expires_in = data.get("data", {}).get("expires_in", 86400)
                if token:
                    # TikTok also returns a new refresh_token
                    new_refresh = data.get("data", {}).get("refresh_token")
                    if new_refresh:
                        acct.platform_refresh_token = new_refresh
                    return token, datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        elif platform == "instagram":
            # Instagram Graph API long-lived token refresh
            resp = httpx.get("https://graph.instagram.com/refresh_access_token", params={
                "grant_type": "ig_refresh_token",
                "access_token": acct.platform_access_token or refresh_token,
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token")
                expires_in = data.get("expires_in", 5184000)  # 60 days default
                if token:
                    return token, datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    except Exception as e:
        logger.error("oauth.platform_refresh_error", platform=platform, error=str(e))

    return None, None
