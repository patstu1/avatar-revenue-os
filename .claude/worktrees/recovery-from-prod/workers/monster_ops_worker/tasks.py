"""Monster Ops workers — expansion advisor, gatekeeper, scale engine recompute."""
import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)


async def _run_all(coro_factory):
    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    for bid in brands:
        try:
            await coro_factory(bid)
        except Exception:
            logger.exception("monster_ops task failed for brand %s", bid)


async def _recompute_expansion(bid):
    from apps.api.services.expansion_advisor_service import recompute_advisory
    async with get_async_session_factory()() as db:
        await recompute_advisory(db, bid)
        await db.commit()


async def _recompute_gatekeeper(bid):
    from apps.api.services.gatekeeper_service import (
        recompute_completion, recompute_truth, recompute_execution_closure,
        recompute_tests, recompute_dependencies, recompute_contradictions,
        recompute_alerts,
    )
    async with get_async_session_factory()() as db:
        await recompute_completion(db, bid)
        await recompute_truth(db, bid)
        await recompute_execution_closure(db, bid)
        await recompute_tests(db, bid)
        await recompute_dependencies(db, bid)
        await recompute_contradictions(db, bid)
        await recompute_alerts(db, bid)
        await db.commit()


async def _recompute_scale(bid):
    from apps.api.services.scale_service import recompute_scale_recommendations
    async with get_async_session_factory()() as db:
        await recompute_scale_recommendations(db, bid)
        await db.commit()


@shared_task(name="workers.monster_ops_worker.tasks.recompute_expansion_advisor", base=TrackedTask)
def recompute_expansion_advisor():
    run_async(_run_all(_recompute_expansion))
    return "expansion-advisor-done"


@shared_task(name="workers.monster_ops_worker.tasks.recompute_gatekeeper", base=TrackedTask)
def recompute_gatekeeper():
    run_async(_run_all(_recompute_gatekeeper))
    return "gatekeeper-done"


@shared_task(name="workers.monster_ops_worker.tasks.recompute_scale_engine", base=TrackedTask)
def recompute_scale_engine():
    run_async(_run_all(_recompute_scale))
    return "scale-engine-done"


async def _run_offer_learning(bid):
    from apps.api.services.offer_learning_service import run_offer_learning
    async with get_async_session_factory()() as db:
        await run_offer_learning(db, bid)
        await db.commit()


@shared_task(name="workers.monster_ops_worker.tasks.run_offer_learning", base=TrackedTask)
def run_offer_learning_task():
    run_async(_run_all(_run_offer_learning))
    return "offer-learning-done"


async def _detect_weak_lanes(bid):
    """Flag weak accounts AND push winners. Full kill/scale decisiveness."""
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.scale_alerts import OperatorAlert
    from packages.db.models.kill_ledger import KillLedgerEntry
    from datetime import datetime, timezone

    async with get_async_session_factory()() as db:
        accounts = list((await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == bid,
                CreatorAccount.is_active.is_(True),
            )
        )).scalars().all())

        if not accounts:
            return {"flagged": 0, "winners": 0}

        now = datetime.now(timezone.utc)
        flagged = 0
        winners_pushed = 0

        avg_ppp = sum(float(a.profit_per_post or 0) for a in accounts) / len(accounts) if accounts else 0

        for acct in accounts:
            ppp = float(acct.profit_per_post or 0)
            imp = int(acct.follower_count or 0)
            ca = acct.created_at
            if ca and ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            age_days = (now - ca).days if ca else 0

            if ppp < 2.0 and imp > 300 and age_days > 30:
                already_killed = (await db.execute(
                    select(KillLedgerEntry).where(
                        KillLedgerEntry.brand_id == bid,
                        KillLedgerEntry.scope_id == acct.id,
                        KillLedgerEntry.is_active.is_(True),
                    ).limit(1)
                )).scalar_one_or_none()

                urgency = 75.0
                if age_days > 60:
                    urgency = 90.0
                if age_days > 90:
                    urgency = 95.0

                if not already_killed:
                    db.add(KillLedgerEntry(
                        brand_id=bid,
                        scope_type="creator_account",
                        scope_id=acct.id,
                        kill_reason=f"Auto-flagged: ${ppp:.2f}/post < $2.00 threshold after {age_days}d with {imp} followers.",
                        performance_snapshot_json={
                            "profit_per_post": ppp, "follower_count": imp, "age_days": age_days,
                            "fatigue_score": float(acct.fatigue_score or 0),
                            "saturation_score": float(acct.saturation_score or 0),
                        },
                        replacement_recommendation_json={"action": "suppress_or_reallocate", "reason": "below_kill_threshold"},
                        confidence_score=0.85,
                    ))

                db.add(OperatorAlert(
                    brand_id=bid,
                    alert_type="weak_lane_auto_kill",
                    title=f"KILL/SUPPRESS: {acct.platform_username} — ${ppp:.2f}/post after {age_days}d",
                    summary=f"{acct.platform_username}: ${ppp:.2f} profit/post, {imp} followers, {age_days}d old. {'ESCALATED — over 60d weak.' if age_days > 60 else 'Below kill threshold.'}",
                    explanation=f"Profit/post ${ppp:.2f} < $2.00. Age {age_days}d. {'Kill ledger entry created.' if not already_killed else 'Already in kill ledger.'}",
                    recommended_action=f"Suppress {acct.platform_username} and reallocate budget to top performers.",
                    confidence=0.85,
                    urgency=urgency,
                ))
                flagged += 1

            elif ppp > avg_ppp * 1.5 and ppp > 5.0 and age_days > 14:
                db.add(OperatorAlert(
                    brand_id=bid,
                    alert_type="winner_scale_push",
                    title=f"SCALE WINNER: {acct.platform_username} — ${ppp:.2f}/post (1.5x avg)",
                    summary=f"{acct.platform_username} outperforms at ${ppp:.2f}/post vs avg ${avg_ppp:.2f}. Push harder.",
                    explanation=f"Top performer: ${ppp:.2f}/post is {ppp/max(avg_ppp,0.01):.1f}x the portfolio average. Current capacity: {acct.posting_capacity_per_day}/day.",
                    recommended_action=f"Increase posting capacity for {acct.platform_username} to {min(acct.posting_capacity_per_day * 2, 10)}/day. Prioritize this account for hero content.",
                    confidence=0.80,
                    urgency=65.0,
                    expected_upside=float(ppp * acct.posting_capacity_per_day * 7),
                ))
                winners_pushed += 1

        if flagged or winners_pushed:
            await db.commit()
        return {"flagged": flagged, "winners": winners_pushed}


async def _trigger_expansion_from_saturation(bid):
    """When avg saturation > 70%, auto-run expansion advisor with launch-window awareness."""
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.scale_alerts import OperatorAlert
    from datetime import datetime, timezone

    async with get_async_session_factory()() as db:
        accounts = list((await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == bid,
                CreatorAccount.is_active.is_(True),
            )
        )).scalars().all())

        if not accounts:
            return {"status": "no_accounts"}

        avg_sat = sum(float(a.saturation_score or 0) for a in accounts) / len(accounts)
        avg_fatigue = sum(float(a.fatigue_score or 0) for a in accounts) / len(accounts)
        all_healthy = all(
            getattr(a.account_health, "value", str(a.account_health)) != "critical"
            for a in accounts
        )

        if avg_sat > 0.7 and all_healthy and avg_fatigue < 0.7:
            from apps.api.services.expansion_advisor_service import recompute_advisory
            result = await recompute_advisory(db, bid)
            await db.commit()

            now = datetime.now(timezone.utc)
            month = now.month
            is_good_launch_window = month not in (12, 1)

            if result.get("should_add") and not is_good_launch_window:
                db.add(OperatorAlert(
                    brand_id=bid,
                    alert_type="expansion_launch_window",
                    title="Expansion recommended but launch window is suboptimal",
                    summary=f"Month {month} is typically weak for new account launches. Consider waiting until February.",
                    recommended_action="Delay launch by 1-2 months unless urgency is critical.",
                    confidence=0.6,
                    urgency=40.0,
                ))
                await db.commit()

            return {"status": "expansion_triggered", "should_add": result.get("should_add"), "good_launch_window": is_good_launch_window}
        elif not all_healthy:
            return {"status": "skipped_unhealthy_accounts"}
        elif avg_fatigue >= 0.7:
            return {"status": "skipped_high_fatigue"}
        else:
            return {"status": "saturation_below_threshold", "avg_saturation": round(avg_sat, 3)}


@shared_task(name="workers.monster_ops_worker.tasks.detect_weak_lanes", base=TrackedTask)
def detect_weak_lanes():
    run_async(_run_all(_detect_weak_lanes))
    return "weak-lanes-done"


@shared_task(name="workers.monster_ops_worker.tasks.trigger_saturation_expansion", base=TrackedTask)
def trigger_saturation_expansion():
    run_async(_run_all(_trigger_expansion_from_saturation))
    return "saturation-expansion-done"


async def _daily_operator_digest(bid):
    """Generate a daily summary of what matters most across ALL system state."""
    from apps.api.services.copilot_service import _copilot_context
    from packages.db.models.copilot import CopilotActionSummary

    async with get_async_session_factory()() as db:
        quick, actions, missing, providers = await _copilot_context(db, bid)

        for action in actions[:20]:
            db.add(CopilotActionSummary(
                brand_id=bid,
                action_type=action.get("action_type", "unknown"),
                urgency=action.get("urgency", "medium"),
                title=action.get("title", "")[:500],
                description=action.get("description", "")[:2000],
                source_module=action.get("source_module", "unknown"),
            ))

        await db.commit()


@shared_task(name="workers.monster_ops_worker.tasks.daily_operator_digest", base=TrackedTask)
def daily_operator_digest():
    run_async(_run_all(_daily_operator_digest))
    return "daily-digest-done"
