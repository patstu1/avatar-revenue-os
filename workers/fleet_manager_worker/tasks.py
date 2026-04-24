"""Fleet manager worker — recompute fleet status, generate expansion recommendations with
specific platform + niche suggestions, persist FleetStatusReport, create operator alerts."""

from __future__ import annotations

import logging
import uuid
from collections import Counter

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.fleet_manager_worker.tasks.recompute_fleet_status")
def recompute_fleet_status(self) -> dict:
    """Count accounts by state, identify best expansion targets, persist reports, notify operator."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from packages.db.enums import HealthStatus
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.autonomous_farm import FleetStatusReport
    from packages.db.models.core import Brand, Organization
    from packages.db.models.publishing import PerformanceMetric
    from packages.db.session import get_sync_engine
    from packages.scoring.niche_research_engine import rank_niches
    from packages.scoring.warmup_engine import determine_warmup_phase

    engine = get_sync_engine()
    fleet_summary: dict[str, int] = {"warming": 0, "scaling": 0, "plateaued": 0, "retired": 0, "suspended": 0}
    expansion_recommendations: list[dict] = []
    brands_processed = 0
    total_revenue_30d = 0.0

    with Session(engine) as session:
        brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()

        for brand in brands:
            try:
                accounts = (
                    session.execute(
                        select(CreatorAccount).where(
                            CreatorAccount.brand_id == brand.id, CreatorAccount.is_active.is_(True)
                        )
                    )
                    .scalars()
                    .all()
                )

                plateaued_accounts = 0
                active_platforms = Counter()
                active_niches = Counter()

                for account in accounts:
                    plat = getattr(account.platform, "value", str(account.platform)) if account.platform else "unknown"
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

                from datetime import datetime, timedelta, timezone

                rev_30d = (
                    session.execute(
                        select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                            PerformanceMetric.brand_id == brand.id,
                            PerformanceMetric.measured_at >= datetime.now(timezone.utc) - timedelta(days=30),
                        )
                    ).scalar()
                    or 0.0
                )
                total_revenue_30d += float(rev_30d)

                if plateaued_accounts > 0 and len(accounts) > 0 and plateaued_accounts / len(accounts) >= 0.3:
                    top_niches = rank_niches(top_n=10)

                    covered_combos = set()
                    for a in accounts:
                        p = getattr(a.platform, "value", str(a.platform)) if a.platform else ""
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
                        "reason": f"{plateaued_accounts}/{len(accounts)} accounts plateaued. Best opportunity: {best_expansion['niche']} on {best_expansion['platform']} (score {best_expansion['composite_score']:.2f})"
                        if best_expansion
                        else "Fleet saturation detected",
                        "suggested_username": f"@{(best_expansion['niche'] if best_expansion else 'new').replace('_', '')}_{uuid.uuid4().hex[:4]}",
                    }
                    expansion_recommendations.append(rec)

                    try:
                        from packages.db.models.scale_alerts import OperatorAlert

                        session.add(
                            OperatorAlert(
                                brand_id=brand.id,
                                alert_type="expansion_recommendation",
                                severity="high",
                                title=f"Add {rec['recommended_platform'].upper()} account in {rec['recommended_niche'].replace('_', ' ')}",
                                description=rec["reason"],
                                operator_action_needed=f"Create a new {rec['recommended_platform']} account for {rec['recommended_niche']} niche. Suggested username: {rec['suggested_username']}",
                            )
                        )
                    except Exception:
                        logger.warning("Could not create operator alert for expansion rec")

                brands_processed += 1
            except Exception:
                logger.exception("Error computing fleet status for brand %s", brand.id)

        total_accounts = sum(fleet_summary.values())
        try:
            orgs = session.execute(select(Organization.id).limit(1)).scalars().all()
            if orgs:
                session.add(
                    FleetStatusReport(
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
                        expansion_details={"recommendations": expansion_recommendations}
                        if expansion_recommendations
                        else {},
                    )
                )
        except Exception:
            logger.warning("Could not persist FleetStatusReport")

        session.commit()

    for rec in expansion_recommendations:
        logger.info(
            "EXPANSION RECOMMENDED: brand=%s platform=%s niche=%s score=%.2f reason=%s",
            rec["brand_name"],
            rec["recommended_platform"],
            rec["recommended_niche"],
            rec["niche_score"],
            rec["reason"],
        )

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "fleet_summary": fleet_summary,
        "total_accounts": total_accounts,
        "total_revenue_30d": round(total_revenue_30d, 2),
        "expansion_recommendations": expansion_recommendations,
    }
