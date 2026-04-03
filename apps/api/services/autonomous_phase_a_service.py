"""Autonomous Execution Phase A — signal scanning, auto queue, warm-up, output & maturity."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.accounts import CreatorAccount
from packages.db.models.autonomous_phase_a import (
    AccountMaturityReport,
    AccountOutputReport,
    AccountWarmupPlan,
    AutoQueueItem,
    NormalizedSignalEvent,
    OutputRampEvent,
    PlatformWarmupPolicy,
    SignalScanRun,
)
from packages.db.models.core import Brand
from packages.db.models.discovery import TopicCandidate, TopicSignal, TrendSignal
from packages.db.models.market_timing import MacroSignalEvent
from packages.db.models.offers import Offer
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.account_warmup_engine import (
    compute_account_output,
    compute_maturity_state,
    compute_output_ramp_event,
    compute_warmup_plan,
    seed_platform_warmup_policies,
)
from packages.scoring.signal_scanning_engine import (
    build_auto_queue_items,
    score_signal_batch,
)


# ---------------------------------------------------------------------------
# Helper serializers
# ---------------------------------------------------------------------------

def _scan_run_out(r: SignalScanRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "scan_type": r.scan_type,
        "status": r.status,
        "signals_detected": r.signals_detected,
        "signals_actionable": r.signals_actionable,
        "scan_duration_ms": r.scan_duration_ms,
        "scan_metadata_json": r.scan_metadata_json,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _signal_event_out(e: NormalizedSignalEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "brand_id": str(e.brand_id),
        "scan_run_id": str(e.scan_run_id) if e.scan_run_id else None,
        "signal_type": e.signal_type,
        "signal_source": e.signal_source,
        "raw_payload_json": e.raw_payload_json,
        "normalized_title": e.normalized_title,
        "normalized_description": e.normalized_description,
        "freshness_score": e.freshness_score,
        "monetization_relevance": e.monetization_relevance,
        "urgency_score": e.urgency_score,
        "confidence": e.confidence,
        "explanation": e.explanation,
        "is_actionable": e.is_actionable,
        "is_active": e.is_active,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _queue_item_out(q: AutoQueueItem) -> dict[str, Any]:
    return {
        "id": str(q.id),
        "brand_id": str(q.brand_id),
        "signal_event_id": str(q.signal_event_id) if q.signal_event_id else None,
        "queue_item_type": q.queue_item_type,
        "target_account_id": str(q.target_account_id) if q.target_account_id else None,
        "target_account_role": q.target_account_role,
        "platform": q.platform,
        "niche": q.niche,
        "sub_niche": q.sub_niche,
        "content_family": q.content_family,
        "monetization_path": q.monetization_path,
        "priority_score": q.priority_score,
        "urgency_score": q.urgency_score,
        "queue_status": q.queue_status,
        "suppression_flags_json": q.suppression_flags_json,
        "hold_reason": q.hold_reason,
        "explanation": q.explanation,
        "is_active": q.is_active,
        "created_at": q.created_at,
        "updated_at": q.updated_at,
    }


def _warmup_plan_out(p: AccountWarmupPlan) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "brand_id": str(p.brand_id),
        "account_id": str(p.account_id),
        "platform": p.platform,
        "warmup_phase": p.warmup_phase,
        "initial_posts_per_week": p.initial_posts_per_week,
        "current_posts_per_week": p.current_posts_per_week,
        "target_posts_per_week": p.target_posts_per_week,
        "warmup_start_date": p.warmup_start_date,
        "warmup_end_date": p.warmup_end_date,
        "engagement_target": p.engagement_target,
        "trust_target": p.trust_target,
        "content_mix_json": p.content_mix_json,
        "failure_signals_json": p.failure_signals_json,
        "ramp_conditions_json": p.ramp_conditions_json,
        "confidence": p.confidence,
        "explanation": p.explanation,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _output_report_out(r: AccountOutputReport) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "account_id": str(r.account_id),
        "platform": r.platform,
        "current_output_per_week": r.current_output_per_week,
        "recommended_output_per_week": r.recommended_output_per_week,
        "max_safe_output_per_week": r.max_safe_output_per_week,
        "max_profitable_output_per_week": r.max_profitable_output_per_week,
        "throttle_reason": r.throttle_reason,
        "next_increase_date": r.next_increase_date,
        "quality_score": r.quality_score,
        "monetization_response_score": r.monetization_response_score,
        "account_health_score": r.account_health_score,
        "saturation_score": r.saturation_score,
        "confidence": r.confidence,
        "explanation": r.explanation,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _maturity_report_out(r: AccountMaturityReport) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "account_id": str(r.account_id),
        "platform": r.platform,
        "maturity_state": r.maturity_state,
        "previous_state": r.previous_state,
        "days_in_current_state": r.days_in_current_state,
        "posts_published": r.posts_published,
        "avg_engagement_rate": r.avg_engagement_rate,
        "follower_velocity": r.follower_velocity,
        "health_score": r.health_score,
        "transition_reason": r.transition_reason,
        "next_expected_transition": r.next_expected_transition,
        "confidence": r.confidence,
        "explanation": r.explanation,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _platform_policy_out(p: PlatformWarmupPolicy) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "platform": p.platform,
        "initial_posts_per_week_min": p.initial_posts_per_week_min,
        "initial_posts_per_week_max": p.initial_posts_per_week_max,
        "warmup_duration_weeks_min": p.warmup_duration_weeks_min,
        "warmup_duration_weeks_max": p.warmup_duration_weeks_max,
        "steady_state_posts_per_week_min": p.steady_state_posts_per_week_min,
        "steady_state_posts_per_week_max": p.steady_state_posts_per_week_max,
        "max_safe_posts_per_day": p.max_safe_posts_per_day,
        "ramp_conditions_json": p.ramp_conditions_json,
        "account_health_signals_json": p.account_health_signals_json,
        "spam_risk_signals_json": p.spam_risk_signals_json,
        "trust_risk_signals_json": p.trust_risk_signals_json,
        "scale_ready_conditions_json": p.scale_ready_conditions_json,
        "ramp_behavior": p.ramp_behavior,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _ramp_event_out(e: OutputRampEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "brand_id": str(e.brand_id),
        "account_id": str(e.account_id),
        "platform": e.platform,
        "event_type": e.event_type,
        "from_output_per_week": e.from_output_per_week,
        "to_output_per_week": e.to_output_per_week,
        "trigger_reason": e.trigger_reason,
        "confidence": e.confidence,
        "explanation": e.explanation,
        "created_at": e.created_at,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _age_hours(dt: Optional[Any]) -> float:
    """Compute hours since a timestamp; defaults to 0 when unavailable."""
    if dt is None:
        return 0.0
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = _utc_now() - dt
        return max(0.0, delta.total_seconds() / 3600)
    except Exception:
        return 0.0


async def _brand_niche(db: AsyncSession, brand_id: uuid.UUID) -> str:
    brand = (
        await db.execute(select(Brand).where(Brand.id == brand_id))
    ).scalar_one_or_none()
    if brand and brand.niche:
        return brand.niche
    return "general"


async def _brand_offers(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(Offer).where(Offer.brand_id == brand_id).limit(100)
            )
        )
        .scalars()
        .all()
    )
    result: list[dict[str, Any]] = []
    for o in rows:
        kws = []
        if isinstance(o.audience_fit_tags, list):
            kws = [str(t) for t in o.audience_fit_tags]
        result.append({"name": o.name, "keywords": kws})
    return result


async def _active_accounts(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[CreatorAccount]:
    return list(
        (
            await db.execute(
                select(CreatorAccount).where(
                    CreatorAccount.brand_id == brand_id,
                )
            )
        )
        .scalars()
        .all()
    )


async def _platform_policies_rows(db: AsyncSession) -> list[PlatformWarmupPolicy]:
    return list(
        (await db.execute(select(PlatformWarmupPolicy).where(PlatformWarmupPolicy.is_active.is_(True))))
        .scalars()
        .all()
    )


async def _ensure_platform_policies(db: AsyncSession) -> list[PlatformWarmupPolicy]:
    rows = await _platform_policies_rows(db)
    if rows:
        return rows
    seeds = seed_platform_warmup_policies()
    for s in seeds:
        p = PlatformWarmupPolicy(
            platform=s["platform"],
            initial_posts_per_week_min=s.get("warmup_cadence", {}).get("week_1", 1),
            initial_posts_per_week_max=s.get("warmup_cadence", {}).get("week_2", 2),
            warmup_duration_weeks_min=2,
            warmup_duration_weeks_max=4,
            steady_state_posts_per_week_min=s.get("posting_cadence_min", 3),
            steady_state_posts_per_week_max=s.get("posting_cadence_max", 14),
            max_safe_posts_per_day=s.get("max_safe_output_per_day", 3),
            ramp_conditions_json={"scale_ready": s.get("scale_ready_conditions", [])},
            account_health_signals_json={"signals": s.get("account_health_signals", [])},
            spam_risk_signals_json={"signals": s.get("spam_fatigue_signals", [])},
            trust_risk_signals_json={},
            scale_ready_conditions_json={"conditions": s.get("scale_ready_conditions", [])},
            ramp_behavior=s.get("ramp_behavior", "moderate"),
        )
        db.add(p)
    await db.flush()
    return await _platform_policies_rows(db)


def _policy_to_engine_dict(p: PlatformWarmupPolicy) -> dict[str, Any]:
    return {
        "platform": p.platform,
        "max_safe_output_per_day": p.max_safe_posts_per_day,
        "warmup_cadence": {
            "week_1": p.initial_posts_per_week_min,
            "week_2": p.initial_posts_per_week_max,
            "week_3_4": p.steady_state_posts_per_week_min,
            "steady_state_min": p.steady_state_posts_per_week_min,
        },
        "scale_ready_conditions": (p.scale_ready_conditions_json or {}).get("conditions", []),
        "spam_fatigue_signals": (p.spam_risk_signals_json or {}).get("signals", []),
        "ramp_behavior": p.ramp_behavior or "moderate",
    }


def _account_to_engine_dict(
    acct: CreatorAccount,
    maturity_report: Optional[AccountMaturityReport] = None,
) -> dict[str, Any]:
    platform_str = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
    age_days = 30
    if hasattr(acct, "created_at") and acct.created_at:
        try:
            created = acct.created_at
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = max(1, (_utc_now() - created).days)
        except Exception:
            logger.debug("account_age_calculation_failed", exc_info=True)

    maturity_state = "stable"
    health_score = 0.5
    days_in_state = 0
    if maturity_report:
        maturity_state = maturity_report.maturity_state or "stable"
        health_score = maturity_report.health_score or 0.5
        days_in_state = maturity_report.days_in_current_state or 0

    return {
        "account_id": str(acct.id),
        "platform": platform_str,
        "role": acct.monetization_focus or "general",
        "niche": acct.niche_focus or "",
        "sub_niche": acct.sub_niche_focus or "",
        "account_age_days": age_days,
        "posts_published": 0,
        "engagement_rate": 0.0,
        "has_violations": False,
        "follower_count": acct.follower_count,
        "current_maturity_state": maturity_state,
        "days_in_current_state": days_in_state,
        "maturity_state": maturity_state,
        "health_score": health_score,
        "current_output_per_week": acct.posting_capacity_per_day,
    }


async def _latest_maturity_map(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[uuid.UUID, AccountMaturityReport]:
    rows = list(
        (
            await db.execute(
                select(AccountMaturityReport).where(
                    AccountMaturityReport.brand_id == brand_id,
                    AccountMaturityReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    best: dict[uuid.UUID, AccountMaturityReport] = {}
    for r in rows:
        existing = best.get(r.account_id)
        if existing is None or (r.created_at and existing.created_at and r.created_at > existing.created_at):
            best[r.account_id] = r
    return best


async def _perf_metrics_for_account(
    db: AsyncSession, account_id: uuid.UUID, days: int = 28,
) -> dict[str, Any]:
    cutoff = _utc_now() - timedelta(days=days)
    rows = list(
        (
            await db.execute(
                select(PerformanceMetric).where(
                    PerformanceMetric.creator_account_id == account_id,
                    PerformanceMetric.measured_at >= cutoff,
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return {
            "posts_last_7d": 0,
            "engagement_rate_7d": 0.0,
            "monetization_revenue_7d": 0.0,
            "monetization_cost_7d": 0.0,
            "follower_delta_7d": 0,
        }
    total_views = sum(r.views for r in rows)
    total_engagement = sum(r.likes + r.comments + r.shares for r in rows)
    eng_rate = total_engagement / total_views if total_views > 0 else 0.0
    total_revenue = sum(r.revenue for r in rows)
    follower_delta = sum(r.followers_gained for r in rows)
    return {
        "posts_last_7d": len(rows),
        "engagement_rate_7d": round(eng_rate, 6),
        "monetization_revenue_7d": round(total_revenue, 2),
        "monetization_cost_7d": 0.0,
        "follower_delta_7d": follower_delta,
    }


async def _perf_history_for_account(
    db: AsyncSession, account_id: uuid.UUID, weeks: int = 8,
) -> list[dict[str, Any]]:
    cutoff = _utc_now() - timedelta(weeks=weeks)
    rows = list(
        (
            await db.execute(
                select(PerformanceMetric).where(
                    PerformanceMetric.creator_account_id == account_id,
                    PerformanceMetric.measured_at >= cutoff,
                ).order_by(PerformanceMetric.measured_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return []
    week_buckets: dict[int, list[PerformanceMetric]] = {}
    for r in rows:
        week_num = (r.measured_at - cutoff).days // 7
        week_buckets.setdefault(week_num, []).append(r)
    history: list[dict[str, Any]] = []
    for wk, items in sorted(week_buckets.items()):
        total_views = sum(i.views for i in items)
        total_eng = sum(i.likes + i.comments + i.shares for i in items)
        history.append({
            "week_number": wk,
            "posts_count": len(items),
            "engagement_rate": total_eng / total_views if total_views > 0 else 0.0,
            "follower_delta": sum(i.followers_gained for i in items),
        })
    return history


# ---------------------------------------------------------------------------
# Gather raw signals from existing discovery & market_timing tables
# ---------------------------------------------------------------------------

async def _gather_raw_signals(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Pull TrendSignals, TopicSignals, and MacroSignalEvents into a list of
    raw signal dicts consumable by score_signal_batch."""
    raw: list[dict[str, Any]] = []

    trend_rows = list(
        (
            await db.execute(
                select(TrendSignal).where(TrendSignal.brand_id == brand_id).limit(200)
            )
        )
        .scalars()
        .all()
    )
    for t in trend_rows:
        meta = t.metadata_blob or {}
        raw.append({
            "title": t.keyword,
            "description": f"Trend signal ({t.signal_type}): {t.keyword}",
            "age_hours": _age_hours(getattr(t, "created_at", None)),
            "keywords": [t.keyword] + meta.get("keywords", []),
            "metrics": {
                "search_volume_delta": t.volume,
                "engagement_velocity": t.velocity,
            },
            "competitive_pressure": 0.3,
            "data_completeness": 0.6 if t.volume > 0 else 0.3,
            "source": "trend_api",
            "signal_type": None,
            "_origin": "trend_signal",
            "_origin_id": str(t.id),
        })

    topic_rows = list(
        (
            await db.execute(
                select(TopicSignal)
                .join(TopicCandidate, TopicSignal.topic_candidate_id == TopicCandidate.id)
                .where(TopicCandidate.brand_id == brand_id)
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    for ts in topic_rows:
        rd = ts.raw_data or {}
        raw.append({
            "title": rd.get("title", ts.signal_type),
            "description": rd.get("description", f"Topic signal: {ts.signal_type}"),
            "age_hours": _age_hours(getattr(ts, "created_at", None)),
            "keywords": rd.get("keywords", [ts.signal_type]),
            "metrics": {
                "engagement_velocity": ts.signal_value,
            },
            "competitive_pressure": 0.2,
            "data_completeness": 0.5,
            "source": ts.signal_source or "internal_analytics",
            "signal_type": None,
            "_origin": "topic_signal",
            "_origin_id": str(ts.id),
        })

    macro_rows = list(
        (
            await db.execute(
                select(MacroSignalEvent).where(
                    (MacroSignalEvent.brand_id == brand_id)
                    | (MacroSignalEvent.brand_id.is_(None))
                ).limit(200)
            )
        )
        .scalars()
        .all()
    )
    for m in macro_rows:
        meta = m.signal_metadata_json or {}
        raw.append({
            "title": meta.get("title", m.signal_type),
            "description": meta.get("description", f"Macro event via {m.source_name}"),
            "age_hours": _age_hours(m.observed_at or getattr(m, "created_at", None)),
            "keywords": meta.get("keywords", [m.signal_type]),
            "metrics": meta.get("metrics", {}),
            "competitive_pressure": float(meta.get("competitive_pressure", 0.4)),
            "data_completeness": float(meta.get("data_completeness", 0.5)),
            "source": "social_listening",
            "signal_type": None,
            "_origin": "macro_signal_event",
            "_origin_id": str(m.id),
        })

    return raw


# ---------------------------------------------------------------------------
# Signal Scanning
# ---------------------------------------------------------------------------

async def run_signal_scan(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    start = _utc_now()
    scan = SignalScanRun(
        brand_id=brand_id,
        scan_type="full",
        status="running",
        signals_detected=0,
        signals_actionable=0,
    )
    db.add(scan)
    await db.flush()

    raw_signals = await _gather_raw_signals(db, brand_id)
    offers = await _brand_offers(db, brand_id)
    niche = await _brand_niche(db, brand_id)

    scored = score_signal_batch(raw_signals, offers, niche)

    events_created = 0
    for s in scored:
        raw_sig = s.get("raw_signal", {})
        evt = NormalizedSignalEvent(
            brand_id=brand_id,
            scan_run_id=scan.id,
            signal_type=s["signal_type"],
            signal_source=s["source"],
            raw_payload_json=raw_sig,
            normalized_title=s["normalized_title"][:500],
            normalized_description=s.get("normalized_description", ""),
            freshness_score=s["freshness_score"],
            monetization_relevance=s["monetization_relevance"],
            urgency_score=s["urgency_score"],
            confidence=s["confidence"],
            explanation=s.get("explanation", ""),
            is_actionable=s["is_actionable"],
        )
        db.add(evt)
        events_created += 1

    elapsed_ms = int((_utc_now() - start).total_seconds() * 1000)
    scan.signals_detected = len(raw_signals)
    scan.signals_actionable = events_created
    scan.scan_duration_ms = elapsed_ms
    scan.status = "completed"
    scan.scan_metadata_json = {
        "raw_count": len(raw_signals),
        "scored_count": len(scored),
        "events_created": events_created,
    }
    await db.flush()
    await db.refresh(scan)
    return _scan_run_out(scan)


async def list_signal_scans(
    db: AsyncSession, brand_id: uuid.UUID, limit: int = 50,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(SignalScanRun)
                .where(SignalScanRun.brand_id == brand_id)
                .order_by(SignalScanRun.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_scan_run_out(r) for r in rows]


async def list_signal_events(
    db: AsyncSession, brand_id: uuid.UUID, limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(NormalizedSignalEvent)
                .where(
                    NormalizedSignalEvent.brand_id == brand_id,
                    NormalizedSignalEvent.is_active.is_(True),
                )
                .order_by(NormalizedSignalEvent.urgency_score.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_signal_event_out(e) for e in rows]


# ---------------------------------------------------------------------------
# Auto Queue Builder
# ---------------------------------------------------------------------------

async def rebuild_auto_queue(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    actionable_rows = list(
        (
            await db.execute(
                select(NormalizedSignalEvent).where(
                    NormalizedSignalEvent.brand_id == brand_id,
                    NormalizedSignalEvent.is_actionable.is_(True),
                    NormalizedSignalEvent.is_active.is_(True),
                ).order_by(NormalizedSignalEvent.urgency_score.desc()).limit(200)
            )
        )
        .scalars()
        .all()
    )

    accounts = await _active_accounts(db, brand_id)
    policies = await _ensure_platform_policies(db)
    maturity_map = await _latest_maturity_map(db, brand_id)

    scored_signals: list[dict[str, Any]] = []
    for evt in actionable_rows:
        scored_signals.append({
            "signal_type": evt.signal_type,
            "source": evt.signal_source,
            "normalized_title": evt.normalized_title,
            "urgency_score": evt.urgency_score,
            "monetization_relevance": evt.monetization_relevance,
            "confidence": evt.confidence,
            "raw_signal": evt.raw_payload_json or {},
            "_event_id": str(evt.id),
        })

    account_dicts: list[dict[str, Any]] = []
    for acct in accounts:
        mr = maturity_map.get(acct.id)
        account_dicts.append(_account_to_engine_dict(acct, mr))

    policy_dicts = [_policy_to_engine_dict(p) for p in policies]

    queue_items = build_auto_queue_items(scored_signals, account_dicts, policy_dicts)

    await db.execute(
        update(AutoQueueItem)
        .where(
            AutoQueueItem.brand_id == brand_id,
            AutoQueueItem.is_active.is_(True),
        )
        .values(is_active=False)
    )

    created_count = 0
    for qi in queue_items:
        target_acct_id = None
        if qi.get("target_account_id"):
            try:
                target_acct_id = uuid.UUID(qi["target_account_id"])
            except (ValueError, TypeError):
                logger.debug("queue_item_target_account_id_parse_failed", exc_info=True)

        signal_event_id = None
        for evt in actionable_rows:
            if evt.normalized_title == qi.get("signal_title"):
                signal_event_id = evt.id
                break

        item = AutoQueueItem(
            brand_id=brand_id,
            signal_event_id=signal_event_id,
            queue_item_type=qi["queue_item_type"],
            target_account_id=target_acct_id,
            target_account_role=qi.get("target_account_role"),
            platform=qi["platform"],
            niche=qi.get("niche", ""),
            sub_niche=qi.get("sub_niche", ""),
            content_family=qi.get("content_family"),
            monetization_path=qi.get("monetization_path"),
            priority_score=qi["priority_score"],
            urgency_score=qi["urgency_score"],
            queue_status=qi["queue_status"],
            suppression_flags_json=qi.get("suppression_flags"),
            hold_reason=qi.get("hold_reason"),
            explanation=qi.get("explanation"),
        )
        db.add(item)
        created_count += 1

    await db.flush()
    return {
        "brand_id": str(brand_id),
        "signals_evaluated": len(actionable_rows),
        "accounts_available": len(accounts),
        "queue_items_created": created_count,
        "old_items_deactivated": True,
    }


async def list_auto_queue(
    db: AsyncSession, brand_id: uuid.UUID, limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AutoQueueItem)
                .where(
                    AutoQueueItem.brand_id == brand_id,
                    AutoQueueItem.is_active.is_(True),
                )
                .order_by(AutoQueueItem.priority_score.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_queue_item_out(q) for q in rows]


# ---------------------------------------------------------------------------
# Account Warm-Up
# ---------------------------------------------------------------------------

async def recompute_warmup(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    accounts = await _active_accounts(db, brand_id)
    policies = await _ensure_platform_policies(db)
    policy_by_platform: dict[str, dict[str, Any]] = {
        _policy_to_engine_dict(p)["platform"]: _policy_to_engine_dict(p) for p in policies
    }

    await db.execute(
        update(AccountWarmupPlan)
        .where(
            AccountWarmupPlan.brand_id == brand_id,
            AccountWarmupPlan.is_active.is_(True),
        )
        .values(is_active=False)
    )

    plans_created = 0
    for acct in accounts:
        acct_dict = _account_to_engine_dict(acct)
        platform_str = acct_dict["platform"]
        policy = policy_by_platform.get(platform_str, policy_by_platform.get("youtube", {}))
        history = await _perf_history_for_account(db, acct.id)

        result = compute_warmup_plan(acct_dict, policy, history)

        plan = AccountWarmupPlan(
            brand_id=brand_id,
            account_id=acct.id,
            platform=platform_str,
            warmup_phase=result["warmup_phase"],
            initial_posts_per_week=result["initial_posts_per_week"],
            current_posts_per_week=result["current_posts_per_week"],
            target_posts_per_week=result.get("target_posts_per_week"),
            engagement_target=result["engagement_target"],
            trust_target=result["trust_target"],
            content_mix_json=result.get("content_mix"),
            failure_signals_json=result.get("failure_signals"),
            ramp_conditions_json=result.get("ramp_conditions"),
            confidence=result.get("confidence", 0.5) if isinstance(result.get("confidence"), (int, float)) else 0.5,
            explanation=result.get("explanation", ""),
        )
        db.add(plan)
        plans_created += 1

    await db.flush()
    return {
        "brand_id": str(brand_id),
        "accounts_processed": len(accounts),
        "warmup_plans_created": plans_created,
    }


async def list_warmup_plans(
    db: AsyncSession, brand_id: uuid.UUID, limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AccountWarmupPlan).where(
                    AccountWarmupPlan.brand_id == brand_id,
                    AccountWarmupPlan.is_active.is_(True),
                ).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_warmup_plan_out(p) for p in rows]


# ---------------------------------------------------------------------------
# Account Output
# ---------------------------------------------------------------------------

async def recompute_account_output(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    warmup_plans = list(
        (
            await db.execute(
                select(AccountWarmupPlan).where(
                    AccountWarmupPlan.brand_id == brand_id,
                    AccountWarmupPlan.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    policies = await _ensure_platform_policies(db)
    policy_by_platform: dict[str, dict[str, Any]] = {
        _policy_to_engine_dict(p)["platform"]: _policy_to_engine_dict(p) for p in policies
    }

    accounts_map: dict[uuid.UUID, CreatorAccount] = {}
    for plan in warmup_plans:
        if plan.account_id not in accounts_map:
            acct = (
                await db.execute(
                    select(CreatorAccount).where(CreatorAccount.id == plan.account_id)
                )
            ).scalar_one_or_none()
            if acct:
                accounts_map[plan.account_id] = acct

    await db.execute(
        update(AccountOutputReport)
        .where(
            AccountOutputReport.brand_id == brand_id,
            AccountOutputReport.is_active.is_(True),
        )
        .values(is_active=False)
    )
    await db.execute(
        update(AccountMaturityReport)
        .where(
            AccountMaturityReport.brand_id == brand_id,
            AccountMaturityReport.is_active.is_(True),
        )
        .values(is_active=False)
    )

    reports_created = 0
    ramp_events_created = 0
    maturity_reports_created = 0

    for plan in warmup_plans:
        acct = accounts_map.get(plan.account_id)
        if not acct:
            continue

        acct_dict = _account_to_engine_dict(acct)
        platform_str = acct_dict["platform"]
        policy = policy_by_platform.get(platform_str, policy_by_platform.get("youtube", {}))
        perf = await _perf_metrics_for_account(db, acct.id)
        history = await _perf_history_for_account(db, acct.id)

        warmup_dict = {
            "warmup_phase": plan.warmup_phase,
            "current_posts_per_week": plan.current_posts_per_week,
            "target_posts_per_week": plan.target_posts_per_week or plan.current_posts_per_week,
        }

        output_result = compute_account_output(acct_dict, warmup_dict, policy, perf)

        next_inc_date = None
        inc_days = output_result.get("next_increase_days")
        if inc_days:
            next_inc_date = _utc_now() + timedelta(days=inc_days)

        report = AccountOutputReport(
            brand_id=brand_id,
            account_id=acct.id,
            platform=platform_str,
            current_output_per_week=output_result["current_output_per_week"],
            recommended_output_per_week=output_result["recommended_output_per_week"],
            max_safe_output_per_week=output_result["max_safe_output_per_week"],
            max_profitable_output_per_week=output_result["max_profitable_output_per_week"],
            throttle_reason=output_result.get("throttle_reason"),
            next_increase_date=next_inc_date,
            quality_score=0.0,
            monetization_response_score=0.0,
            account_health_score=output_result.get("health_score", 0.0),
            saturation_score=acct.saturation_score,
            confidence=output_result.get("confidence", 0.5) if isinstance(output_result.get("confidence"), (int, float)) else 0.5,
            explanation=output_result.get("explanation", ""),
        )
        db.add(report)
        reports_created += 1

        maturity_result = compute_maturity_state(acct_dict, history, policy)
        mat_report = AccountMaturityReport(
            brand_id=brand_id,
            account_id=acct.id,
            platform=platform_str,
            maturity_state=maturity_result["maturity_state"],
            previous_state=maturity_result.get("previous_state"),
            days_in_current_state=maturity_result["days_in_current_state"],
            posts_published=maturity_result["posts_published"],
            avg_engagement_rate=maturity_result["avg_engagement_rate"],
            follower_velocity=maturity_result["follower_velocity"],
            health_score=maturity_result["health_score"],
            transition_reason=maturity_result.get("explanation", ""),
            next_expected_transition=None,
            confidence=maturity_result.get("confidence", 0.5) if isinstance(maturity_result.get("confidence"), (int, float)) else 0.5,
            explanation=maturity_result.get("explanation", ""),
        )
        db.add(mat_report)
        maturity_reports_created += 1

        ramp = compute_output_ramp_event(
            current_output=int(output_result["current_output_per_week"]),
            account_maturity=maturity_result,
            platform_policy=policy,
            account_health=maturity_result["health_score"],
        )
        if ramp:
            evt = OutputRampEvent(
                brand_id=brand_id,
                account_id=acct.id,
                platform=platform_str,
                event_type=ramp["event_type"],
                from_output_per_week=ramp["from_output"],
                to_output_per_week=ramp["to_output"],
                trigger_reason=ramp.get("reason"),
                confidence=ramp.get("confidence", 0.5),
                explanation=ramp.get("reason", ""),
            )
            db.add(evt)
            ramp_events_created += 1

    await db.flush()
    return {
        "brand_id": str(brand_id),
        "output_reports_created": reports_created,
        "maturity_reports_created": maturity_reports_created,
        "ramp_events_created": ramp_events_created,
    }


async def list_account_output(
    db: AsyncSession, brand_id: uuid.UUID, limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AccountOutputReport).where(
                    AccountOutputReport.brand_id == brand_id,
                    AccountOutputReport.is_active.is_(True),
                ).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_output_report_out(r) for r in rows]


# ---------------------------------------------------------------------------
# Platform Warmup Policies
# ---------------------------------------------------------------------------

async def list_account_maturity(
    db: AsyncSession, brand_id: uuid.UUID,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AccountMaturityReport).where(
                    AccountMaturityReport.brand_id == brand_id,
                    AccountMaturityReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return [_maturity_report_out(r) for r in rows]


list_account_warmup = list_warmup_plans


# ---------------------------------------------------------------------------
# Platform Warmup Policies
# ---------------------------------------------------------------------------

async def list_platform_warmup_policies(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    policies = await _ensure_platform_policies(db)
    return [_platform_policy_out(p) for p in policies]
