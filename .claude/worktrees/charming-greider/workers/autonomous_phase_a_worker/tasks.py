"""Autonomous Phase A recurring workers — signal scan, queue build, warmup, output, maturity."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from workers.celery_app import app
from workers.base_task import TrackedTask
from packages.db.session import get_sync_engine
from packages.db.models.core import Brand
from packages.db.models.accounts import CreatorAccount
from packages.db.models.discovery import TrendSignal, TopicSignal, TopicCandidate
from packages.db.models.market_timing import MacroSignalEvent
from packages.db.models.autonomous_phase_a import (
    SignalScanRun,
    NormalizedSignalEvent,
    AutoQueueItem,
    AccountWarmupPlan,
    AccountOutputReport,
    AccountMaturityReport,
    PlatformWarmupPolicy,
    OutputRampEvent,
)
from packages.scoring.signal_scanning_engine import score_signal_batch, build_auto_queue_items
from packages.scoring.account_warmup_engine import (
    compute_warmup_plan,
    compute_account_output,
    compute_maturity_state,
    compute_output_ramp_event,
    seed_platform_warmup_policies,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_warmup_policies_seeded(session: Session) -> None:
    """Seed PlatformWarmupPolicy rows from platform specs when the table is empty."""
    count = session.execute(
        select(func.count()).select_from(PlatformWarmupPolicy)
    ).scalar() or 0
    if count > 0:
        return

    for sp in seed_platform_warmup_policies():
        wc = sp.get("warmup_cadence", {})
        session.add(PlatformWarmupPolicy(
            platform=sp["platform"],
            initial_posts_per_week_min=wc.get("week_1", 1),
            initial_posts_per_week_max=wc.get("week_2", 3),
            steady_state_posts_per_week_min=sp.get("posting_cadence_min", 3),
            steady_state_posts_per_week_max=sp.get("posting_cadence_max", 14),
            max_safe_posts_per_day=sp.get("max_safe_output_per_day", 3),
            ramp_conditions_json=sp.get("expansion_conditions"),
            account_health_signals_json=sp.get("account_health_signals"),
            spam_risk_signals_json=sp.get("spam_fatigue_signals"),
            trust_risk_signals_json=sp.get("saturation_indicators"),
            scale_ready_conditions_json=sp.get("scale_ready_conditions"),
            ramp_behavior=sp.get("ramp_behavior", "moderate"),
        ))
    session.flush()
    logger.info("warmup_policies.seeded")


def _trend_to_raw(sig: TrendSignal, now: datetime) -> dict:
    age_h = (now - sig.created_at).total_seconds() / 3600 if sig.created_at else 0
    meta = sig.metadata_blob or {}
    return {
        "title": sig.keyword,
        "description": meta.get("description", ""),
        "age_hours": age_h,
        "keywords": [sig.keyword] + meta.get("keywords", []),
        "signal_type": sig.signal_type,
        "source": "trend_api",
        "metrics": {
            "search_volume_delta": float(sig.volume),
            "engagement_velocity": float(sig.velocity),
        },
        "competitive_pressure": meta.get("competitive_pressure", 0.3),
        "data_completeness": 0.7 if sig.is_actionable else 0.4,
    }


def _topic_to_raw(ts: TopicSignal, now: datetime) -> dict:
    raw = ts.raw_data or {}
    age_h = (now - ts.created_at).total_seconds() / 3600 if ts.created_at else 0
    return {
        "title": raw.get("title", ts.signal_type),
        "description": raw.get("description", ""),
        "age_hours": age_h,
        "keywords": raw.get("keywords", []),
        "signal_type": ts.signal_type,
        "source": ts.signal_source or "internal_analytics",
        "metrics": raw.get("metrics", {}),
        "competitive_pressure": raw.get("competitive_pressure", 0.2),
        "data_completeness": raw.get("data_completeness", 0.5),
    }


def _macro_to_raw(ev: MacroSignalEvent, now: datetime) -> dict:
    ref = ev.observed_at or ev.created_at
    age_h = (now - ref).total_seconds() / 3600 if ref else 0
    meta = ev.signal_metadata_json or {}
    return {
        "title": meta.get("title", ev.signal_type),
        "description": meta.get("description", ""),
        "age_hours": age_h,
        "keywords": meta.get("keywords", []),
        "signal_type": ev.signal_type,
        "source": ev.source_name,
        "metrics": meta.get("metrics", {}),
        "competitive_pressure": meta.get("competitive_pressure", 0.2),
        "data_completeness": meta.get("data_completeness", 0.5),
    }


def _account_dict(
    acct: CreatorAccount,
    maturity: AccountMaturityReport | None = None,
) -> dict:
    age_days = (datetime.now(timezone.utc) - acct.created_at).days if acct.created_at else 0
    platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
    return {
        "account_id": str(acct.id),
        "platform": platform,
        "role": acct.scale_role or "general",
        "niche": acct.niche_focus or "",
        "sub_niche": acct.sub_niche_focus or "",
        "account_age_days": age_days,
        "posts_published": maturity.posts_published if maturity else 0,
        "engagement_rate": maturity.avg_engagement_rate if maturity else 0.0,
        "has_violations": False,
        "follower_count": acct.follower_count or 0,
        "maturity_state": maturity.maturity_state if maturity else "warming",
        "health_score": maturity.health_score if maturity else 0.5,
        "current_output_per_week": (acct.posting_capacity_per_day or 1) * 7,
        "current_maturity_state": maturity.maturity_state if maturity else None,
        "days_in_current_state": maturity.days_in_current_state if maturity else 0,
    }


def _policy_dict(policy: PlatformWarmupPolicy) -> dict:
    return {
        "platform": policy.platform,
        "warmup_cadence": {
            "week_1": policy.initial_posts_per_week_min,
            "week_2": policy.initial_posts_per_week_max,
            "week_3_4": policy.steady_state_posts_per_week_min,
            "steady_state_min": policy.steady_state_posts_per_week_min,
        },
        "max_safe_output_per_day": policy.max_safe_posts_per_day,
        "scale_ready_conditions": policy.scale_ready_conditions_json or [],
        "spam_fatigue_signals": policy.spam_risk_signals_json or [],
        "ramp_behavior": policy.ramp_behavior or "moderate",
        "suppressed_signal_types": [],
    }


# ---------------------------------------------------------------------------
# Task 1 — Signal Scan
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_a_worker.tasks.run_all_signal_scans")
def run_all_signal_scans(self) -> dict:
    """Gather TrendSignal, TopicSignal, MacroSignalEvent per brand, score, and persist."""
    engine = get_sync_engine()
    brands_processed = 0
    signals_created = 0
    errors: list[dict] = []
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        for brand in brands:
            try:
                trends = session.execute(
                    select(TrendSignal).where(TrendSignal.brand_id == brand.id)
                ).scalars().all()

                topic_sigs = session.execute(
                    select(TopicSignal)
                    .join(TopicCandidate, TopicSignal.topic_candidate_id == TopicCandidate.id)
                    .where(TopicCandidate.brand_id == brand.id)
                ).scalars().all()

                macro_events = session.execute(
                    select(MacroSignalEvent).where(
                        (MacroSignalEvent.brand_id == brand.id)
                        | (MacroSignalEvent.brand_id.is_(None))
                    )
                ).scalars().all()

                raw_signals: list[dict] = []
                for t in trends:
                    raw_signals.append(_trend_to_raw(t, now))
                for ts in topic_sigs:
                    raw_signals.append(_topic_to_raw(ts, now))
                for me in macro_events:
                    raw_signals.append(_macro_to_raw(me, now))

                if not raw_signals:
                    brands_processed += 1
                    continue

                brand_offers: list[dict] = []
                guidelines = brand.brand_guidelines or {}
                if isinstance(guidelines, dict):
                    for offer in guidelines.get("offers", []):
                        brand_offers.append({
                            "name": offer.get("name", ""),
                            "keywords": offer.get("keywords", []),
                        })

                scored = score_signal_batch(raw_signals, brand_offers, brand.niche or "")

                scan_run = SignalScanRun(
                    brand_id=brand.id,
                    scan_type="full_scan",
                    status="completed",
                    signals_detected=len(raw_signals),
                    signals_actionable=len(scored),
                    scan_metadata_json={
                        "trend_count": len(trends),
                        "topic_count": len(topic_sigs),
                        "macro_count": len(macro_events),
                    },
                )
                session.add(scan_run)
                session.flush()

                for s in scored:
                    session.add(NormalizedSignalEvent(
                        brand_id=brand.id,
                        scan_run_id=scan_run.id,
                        signal_type=s["signal_type"],
                        signal_source=s["source"],
                        raw_payload_json=s.get("raw_signal"),
                        normalized_title=s["normalized_title"],
                        normalized_description=s["normalized_description"],
                        freshness_score=s["freshness_score"],
                        monetization_relevance=s["monetization_relevance"],
                        urgency_score=s["urgency_score"],
                        confidence=s["confidence"],
                        explanation=s["explanation"],
                        is_actionable=True,
                    ))
                    signals_created += 1

                brands_processed += 1
                logger.info(
                    "signal_scan.brand_done",
                    brand_id=str(brand.id),
                    raw=len(raw_signals),
                    actionable=len(scored),
                )
            except Exception as exc:
                logger.exception("signal_scan.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "signals_created": signals_created,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Task 2 — Auto Queue Rebuild
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_a_worker.tasks.rebuild_all_auto_queues")
def rebuild_all_auto_queues(self) -> dict:
    """Build posting queue from actionable signals, matching to accounts."""
    engine = get_sync_engine()
    brands_processed = 0
    items_created = 0
    errors: list[dict] = []

    with Session(engine) as session:
        _ensure_warmup_policies_seeded(session)

        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        policies = session.execute(
            select(PlatformWarmupPolicy).where(PlatformWarmupPolicy.is_active.is_(True))
        ).scalars().all()
        policy_dicts = [_policy_dict(p) for p in policies]

        for brand in brands:
            try:
                actionable = session.execute(
                    select(NormalizedSignalEvent).where(
                        NormalizedSignalEvent.brand_id == brand.id,
                        NormalizedSignalEvent.is_actionable.is_(True),
                        NormalizedSignalEvent.is_active.is_(True),
                    )
                ).scalars().all()

                if not actionable:
                    brands_processed += 1
                    continue

                accounts = session.execute(
                    select(CreatorAccount).where(
                        CreatorAccount.brand_id == brand.id,
                        CreatorAccount.is_active.is_(True),
                    )
                ).scalars().all()

                maturity_rows = session.execute(
                    select(AccountMaturityReport).where(
                        AccountMaturityReport.brand_id == brand.id,
                        AccountMaturityReport.is_active.is_(True),
                    )
                ).scalars().all()
                maturity_map: dict[str, AccountMaturityReport] = {
                    str(mr.account_id): mr for mr in maturity_rows
                }

                account_dicts = [
                    _account_dict(a, maturity_map.get(str(a.id)))
                    for a in accounts
                ]

                scored_signals = [
                    {
                        "signal_type": ev.signal_type,
                        "normalized_title": ev.normalized_title,
                        "urgency_score": ev.urgency_score,
                        "monetization_relevance": ev.monetization_relevance,
                        "freshness_score": ev.freshness_score,
                        "confidence": ev.confidence,
                        "raw_signal": ev.raw_payload_json or {},
                    }
                    for ev in actionable
                ]

                queue_items = build_auto_queue_items(scored_signals, account_dicts, policy_dicts)

                session.execute(
                    update(AutoQueueItem)
                    .where(
                        AutoQueueItem.brand_id == brand.id,
                        AutoQueueItem.is_active.is_(True),
                    )
                    .values(is_active=False)
                )

                for qi in queue_items:
                    target_id = qi.get("target_account_id")
                    session.add(AutoQueueItem(
                        brand_id=brand.id,
                        queue_item_type=qi["queue_item_type"],
                        target_account_id=_uuid.UUID(target_id) if target_id else None,
                        target_account_role=qi.get("target_account_role"),
                        platform=qi["platform"],
                        niche=qi.get("niche", ""),
                        sub_niche=qi.get("sub_niche"),
                        content_family=qi.get("content_family"),
                        monetization_path=qi.get("monetization_path"),
                        priority_score=qi["priority_score"],
                        urgency_score=qi["urgency_score"],
                        queue_status=qi["queue_status"],
                        suppression_flags_json=qi.get("suppression_flags"),
                        hold_reason=qi.get("hold_reason"),
                        explanation=qi.get("explanation"),
                    ))
                    items_created += 1

                brands_processed += 1
                logger.info(
                    "auto_queue.brand_done",
                    brand_id=str(brand.id),
                    items=len(queue_items),
                )
            except Exception as exc:
                logger.exception("auto_queue.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "items_created": items_created,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Task 3 — Warmup Recompute
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_a_worker.tasks.recompute_all_warmup")
def recompute_all_warmup(self) -> dict:
    """Recompute warmup plans for all active accounts across all brands."""
    engine = get_sync_engine()
    brands_processed = 0
    plans_created = 0
    errors: list[dict] = []

    with Session(engine) as session:
        _ensure_warmup_policies_seeded(session)

        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        policies = session.execute(
            select(PlatformWarmupPolicy).where(PlatformWarmupPolicy.is_active.is_(True))
        ).scalars().all()
        policy_by_platform = {p.platform: _policy_dict(p) for p in policies}

        for brand in brands:
            try:
                accounts = session.execute(
                    select(CreatorAccount).where(
                        CreatorAccount.brand_id == brand.id,
                        CreatorAccount.is_active.is_(True),
                    )
                ).scalars().all()

                session.execute(
                    update(AccountWarmupPlan)
                    .where(
                        AccountWarmupPlan.brand_id == brand.id,
                        AccountWarmupPlan.is_active.is_(True),
                    )
                    .values(is_active=False)
                )

                for acct in accounts:
                    platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
                    policy = policy_by_platform.get(platform, policy_by_platform.get("youtube", {}))
                    if not policy:
                        continue

                    acct_d = _account_dict(acct)
                    result = compute_warmup_plan(acct_d, policy, [])

                    session.add(AccountWarmupPlan(
                        brand_id=brand.id,
                        account_id=acct.id,
                        platform=platform,
                        warmup_phase=result["warmup_phase"],
                        initial_posts_per_week=result["initial_posts_per_week"],
                        current_posts_per_week=result["current_posts_per_week"],
                        target_posts_per_week=result["target_posts_per_week"],
                        engagement_target=result["engagement_target"],
                        trust_target=result["trust_target"],
                        content_mix_json=result.get("content_mix"),
                        failure_signals_json=result.get("failure_signals"),
                        ramp_conditions_json=result.get("ramp_conditions"),
                        confidence=0.7,
                        explanation=result["explanation"],
                    ))
                    plans_created += 1

                brands_processed += 1
                logger.info(
                    "warmup.brand_done",
                    brand_id=str(brand.id),
                    plans=len(accounts),
                )
            except Exception as exc:
                logger.exception("warmup.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "plans_created": plans_created,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Task 4 — Output Recompute
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_a_worker.tasks.recompute_all_output")
def recompute_all_output(self) -> dict:
    """Recompute output reports and ramp events for all active warmup plans."""
    engine = get_sync_engine()
    brands_processed = 0
    reports_upserted = 0
    ramp_events_created = 0
    errors: list[dict] = []

    with Session(engine) as session:
        _ensure_warmup_policies_seeded(session)

        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        policies = session.execute(
            select(PlatformWarmupPolicy).where(PlatformWarmupPolicy.is_active.is_(True))
        ).scalars().all()
        policy_by_platform = {p.platform: _policy_dict(p) for p in policies}

        for brand in brands:
            try:
                plans = session.execute(
                    select(AccountWarmupPlan).where(
                        AccountWarmupPlan.brand_id == brand.id,
                        AccountWarmupPlan.is_active.is_(True),
                    )
                ).scalars().all()

                for plan in plans:
                    acct = session.get(CreatorAccount, plan.account_id)
                    if not acct or not acct.is_active:
                        continue

                    platform = plan.platform
                    policy = policy_by_platform.get(platform, policy_by_platform.get("youtube", {}))
                    if not policy:
                        continue

                    acct_d = _account_dict(acct)
                    plan_d = {
                        "warmup_phase": plan.warmup_phase,
                        "current_posts_per_week": plan.current_posts_per_week,
                        "target_posts_per_week": plan.target_posts_per_week,
                    }
                    perf = {
                        "posts_last_7d": plan.current_posts_per_week,
                        "engagement_rate_7d": 0.0,
                        "monetization_revenue_7d": 0.0,
                        "monetization_cost_7d": 0.0,
                        "follower_delta_7d": 0,
                    }

                    output = compute_account_output(acct_d, plan_d, policy, perf)

                    session.execute(
                        update(AccountOutputReport)
                        .where(
                            AccountOutputReport.brand_id == brand.id,
                            AccountOutputReport.account_id == acct.id,
                            AccountOutputReport.is_active.is_(True),
                        )
                        .values(is_active=False)
                    )

                    session.add(AccountOutputReport(
                        brand_id=brand.id,
                        account_id=acct.id,
                        platform=platform,
                        current_output_per_week=output["current_output_per_week"],
                        recommended_output_per_week=output["recommended_output_per_week"],
                        max_safe_output_per_week=output["max_safe_output_per_week"],
                        max_profitable_output_per_week=output["max_profitable_output_per_week"],
                        throttle_reason=output.get("throttle_reason"),
                        quality_score=0.5,
                        monetization_response_score=0.0,
                        account_health_score=output["health_score"],
                        saturation_score=0.0,
                        confidence=0.7,
                        explanation=output["explanation"],
                    ))
                    reports_upserted += 1

                    maturity_row = session.execute(
                        select(AccountMaturityReport).where(
                            AccountMaturityReport.account_id == acct.id,
                            AccountMaturityReport.is_active.is_(True),
                        )
                    ).scalars().first()

                    maturity_d = {
                        "maturity_state": maturity_row.maturity_state if maturity_row else "warming",
                        "platform": platform,
                    }

                    ramp = compute_output_ramp_event(
                        output["current_output_per_week"],
                        maturity_d,
                        policy,
                        output["health_score"],
                    )
                    if ramp:
                        session.add(OutputRampEvent(
                            brand_id=brand.id,
                            account_id=acct.id,
                            platform=platform,
                            event_type=ramp["event_type"],
                            from_output_per_week=ramp["from_output"],
                            to_output_per_week=ramp["to_output"],
                            trigger_reason=ramp["reason"],
                            confidence=ramp["confidence"],
                            explanation=ramp["reason"],
                        ))
                        ramp_events_created += 1

                brands_processed += 1
                logger.info(
                    "output.brand_done",
                    brand_id=str(brand.id),
                    reports=reports_upserted,
                    ramp_events=ramp_events_created,
                )
            except Exception as exc:
                logger.exception("output.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "reports_upserted": reports_upserted,
        "ramp_events_created": ramp_events_created,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Task 5 — Maturity Recompute
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_a_worker.tasks.recompute_all_maturity")
def recompute_all_maturity(self) -> dict:
    """Recompute maturity state for all active accounts across all brands."""
    engine = get_sync_engine()
    brands_processed = 0
    reports_upserted = 0
    errors: list[dict] = []

    with Session(engine) as session:
        _ensure_warmup_policies_seeded(session)

        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        policies = session.execute(
            select(PlatformWarmupPolicy).where(PlatformWarmupPolicy.is_active.is_(True))
        ).scalars().all()
        policy_by_platform = {p.platform: _policy_dict(p) for p in policies}

        for brand in brands:
            try:
                accounts = session.execute(
                    select(CreatorAccount).where(
                        CreatorAccount.brand_id == brand.id,
                        CreatorAccount.is_active.is_(True),
                    )
                ).scalars().all()

                for acct in accounts:
                    platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
                    policy = policy_by_platform.get(platform, policy_by_platform.get("youtube", {}))
                    if not policy:
                        continue

                    existing = session.execute(
                        select(AccountMaturityReport).where(
                            AccountMaturityReport.account_id == acct.id,
                            AccountMaturityReport.is_active.is_(True),
                        )
                    ).scalars().first()

                    acct_d = _account_dict(acct, existing)
                    result = compute_maturity_state(acct_d, [], policy)

                    if existing:
                        session.execute(
                            update(AccountMaturityReport)
                            .where(
                                AccountMaturityReport.account_id == acct.id,
                                AccountMaturityReport.is_active.is_(True),
                            )
                            .values(is_active=False)
                        )

                    transition_reason = result["explanation"] if result.get("state_changed") else None
                    session.add(AccountMaturityReport(
                        brand_id=brand.id,
                        account_id=acct.id,
                        platform=platform,
                        maturity_state=result["maturity_state"],
                        previous_state=result.get("previous_state"),
                        days_in_current_state=result["days_in_current_state"],
                        posts_published=result["posts_published"],
                        avg_engagement_rate=result["avg_engagement_rate"],
                        follower_velocity=result["follower_velocity"],
                        health_score=result["health_score"],
                        transition_reason=transition_reason,
                        confidence=0.7,
                        explanation=result["explanation"],
                    ))
                    reports_upserted += 1

                brands_processed += 1
                logger.info(
                    "maturity.brand_done",
                    brand_id=str(brand.id),
                    accounts=len(accounts),
                )
            except Exception as exc:
                logger.exception("maturity.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {
        "status": "completed",
        "brands_processed": brands_processed,
        "reports_upserted": reports_upserted,
        "errors": errors,
    }
