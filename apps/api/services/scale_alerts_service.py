"""Scale alerts service: alerts, launch candidates, blockers, readiness, notifications.

Architecture: recompute_* functions are WRITE paths (POST only).
All get_* functions are READ-ONLY. acknowledge/resolve are targeted mutations.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.portfolio import (
    RevenueLeakReport, ScaleRecommendation, TrustSignalReport,
)
from packages.db.models.scale_alerts import (
    LaunchCandidate, LaunchReadinessReport, NotificationDelivery,
    OperatorAlert, ScaleBlockerReport,
)
from packages.notifications.adapters import NotificationPayload
from packages.scoring.scale_alerts_engine import (
    EXPANSION_ALERT_TYPES,
    compute_launch_readiness,
    diagnose_scale_blockers,
    generate_launch_candidates,
    generate_scale_alerts,
)

AccessError = Literal["not_found", "forbidden"]


def _acct_dicts(accounts: list) -> list[dict]:
    return [{
        "id": str(a.id), "platform": a.platform.value if hasattr(a.platform, "value") else str(a.platform),
        "geography": a.geography, "language": a.language, "niche_focus": a.niche_focus,
        "username": a.platform_username, "follower_count": a.follower_count,
        "fatigue_score": float(a.fatigue_score or 0), "saturation_score": float(a.saturation_score or 0),
        "originality_drift_score": float(a.originality_drift_score or 0),
        "account_health": a.account_health.value if hasattr(a.account_health, "value") else str(a.account_health),
        "ctr": float(a.ctr or 0), "conversion_rate": float(a.conversion_rate or 0),
        "posting_capacity_per_day": a.posting_capacity_per_day,
    } for a in accounts]


async def _brand_context(db: AsyncSession, brand_id: uuid.UUID):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")
    accounts = list((await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True)))).scalars().all())
    offers = list((await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all())
    scale_rec = (await db.execute(select(ScaleRecommendation).where(ScaleRecommendation.brand_id == brand_id).order_by(ScaleRecommendation.created_at.desc()).limit(1))).scalars().first()
    trust_rows = list((await db.execute(select(TrustSignalReport).where(TrustSignalReport.brand_id == brand_id))).scalars().all())
    trust_avg = round(sum(t.trust_score for t in trust_rows) / max(1, len(trust_rows)), 1) if trust_rows else 60.0
    leak_count = (await db.execute(select(func.count()).select_from(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand_id, RevenueLeakReport.is_resolved.is_(False)))).scalar() or 0

    acc_dicts = _acct_dicts(accounts)
    scale_dict = {}
    cann_risk = 0.12
    aud_sep = 0.85
    if scale_rec:
        scale_dict = {
            "recommendation_key": scale_rec.recommendation_key,
            "scale_readiness_score": scale_rec.scale_readiness_score,
            "incremental_profit_new_account": scale_rec.incremental_profit_new_account,
            "incremental_profit_existing_push": scale_rec.incremental_profit_existing_push,
            "explanation": scale_rec.explanation,
            "best_next_account": scale_rec.best_next_account or {},
            "id": str(scale_rec.id),
        }
        cann_risk = scale_rec.cannibalization_risk_score
        aud_sep = scale_rec.audience_segment_separation

    return brand, accounts, acc_dicts, offers, scale_rec, scale_dict, trust_avg, leak_count, cann_risk, aud_sep


# ---------------------------------------------------------------------------
# WRITE: Alerts
# ---------------------------------------------------------------------------

def _outbound_channels_for_alert(urgency: float) -> list[str]:
    if urgency < 55:
        return []
    return ["email", "slack"]


async def recompute_alerts(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand, accounts, acc_dicts, offers, scale_rec, scale_dict, trust_avg, leak_count, cann_risk, aud_sep = await _brand_context(db, brand_id)
    # Clean pending notifications for alerts being replaced (idempotency)
    await db.execute(delete(NotificationDelivery).where(
        NotificationDelivery.brand_id == brand_id,
        NotificationDelivery.status == "pending",
    ))
    # Replace active workflow states; keep resolved history for audit
    await db.execute(delete(OperatorAlert).where(
        OperatorAlert.brand_id == brand_id,
        OperatorAlert.status.in_(("unread", "acknowledged")),
    ))

    alerts_data = generate_scale_alerts(
        scale_dict, acc_dicts, trust_avg, leak_count, cann_risk,
        [float(a.saturation_score or 0) for a in accounts],
        [float(a.fatigue_score or 0) for a in accounts],
        [float(a.originality_drift_score or 0) for a in accounts],
    )
    created: list[OperatorAlert] = []
    for ad in alerts_data:
        alert = OperatorAlert(
            brand_id=brand_id, alert_type=ad["alert_type"], title=ad["title"],
            summary=ad["summary"], explanation=ad.get("explanation"),
            recommended_action=ad.get("recommended_action"),
            confidence=ad["confidence"], urgency=ad["urgency"],
            expected_upside=ad["expected_upside"], expected_cost=ad["expected_cost"],
            expected_time_to_signal_days=ad["expected_time_to_signal_days"],
            supporting_metrics=ad.get("supporting_metrics"),
            blocking_factors=ad.get("blocking_factors"),
            linked_scale_recommendation_id=uuid.UUID(scale_dict["id"]) if scale_dict.get("id") else None,
        )
        db.add(alert)
        await db.flush()
        created.append(alert)
        db.add(NotificationDelivery(
            brand_id=brand_id, alert_id=alert.id, channel="in_app",
            payload={"title": ad["title"], "summary": ad["summary"], "urgency": ad["urgency"], "alert_type": ad["alert_type"]},
            status="delivered", attempts=1,
            delivered_at=datetime.now(timezone.utc).isoformat(),
        ))
        payload = NotificationPayload(
            title=ad["title"], summary=ad["summary"], urgency=float(ad["urgency"]),
            alert_type=ad["alert_type"], brand_id=str(brand_id), alert_id=str(alert.id),
            detail_url=f"/dashboard/scale?brand={brand_id}",
        )
        for ch in _outbound_channels_for_alert(float(ad["urgency"])):
            db.add(NotificationDelivery(
                brand_id=brand_id, alert_id=alert.id, channel=ch,
                payload=payload.to_dict(), status="pending", attempts=0,
            ))

    top_c = (await db.execute(
        select(LaunchCandidate).where(
            LaunchCandidate.brand_id == brand_id, LaunchCandidate.is_active.is_(True),
        ).order_by(LaunchCandidate.urgency.desc()).limit(1)
    )).scalars().first()
    if top_c:
        for al in created:
            if al.alert_type in EXPANSION_ALERT_TYPES:
                al.linked_launch_candidate_id = top_c.id

    await db.flush()
    return {"alerts_created": len(alerts_data)}


# ---------------------------------------------------------------------------
# WRITE: Launch Candidates
# ---------------------------------------------------------------------------

async def recompute_launch_candidates(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand, accounts, acc_dicts, offers, scale_rec, scale_dict, trust_avg, leak_count, cann_risk, aud_sep = await _brand_context(db, brand_id)
    await db.execute(delete(LaunchCandidate).where(LaunchCandidate.brand_id == brand_id))

    offer_dicts = [{"id": str(o.id), "name": o.name} for o in offers]
    candidates = generate_launch_candidates(scale_dict, acc_dicts, brand.niche, cann_risk, aud_sep, offer_dicts)
    for cd in candidates:
        lc = LaunchCandidate(
            brand_id=brand_id, candidate_type=cd["candidate_type"],
            primary_platform=cd["primary_platform"], secondary_platform=cd.get("secondary_platform"),
            niche=cd["niche"], sub_niche=cd.get("sub_niche"),
            language=cd["language"], geography=cd["geography"],
            avatar_persona_strategy=cd.get("avatar_persona_strategy"),
            monetization_path=cd.get("monetization_path"),
            content_style=cd.get("content_style"), posting_strategy=cd.get("posting_strategy"),
            expected_monthly_revenue_min=cd["expected_monthly_revenue_min"],
            expected_monthly_revenue_max=cd["expected_monthly_revenue_max"],
            expected_launch_cost=cd["expected_launch_cost"],
            expected_time_to_signal_days=cd["expected_time_to_signal_days"],
            expected_time_to_profit_days=cd["expected_time_to_profit_days"],
            cannibalization_risk=cd["cannibalization_risk"],
            audience_separation_score=cd["audience_separation_score"],
            confidence=cd["confidence"], urgency=cd["urgency"],
            supporting_reasons=cd["supporting_reasons"],
            required_resources=cd["required_resources"],
            launch_blockers=cd["launch_blockers"],
            linked_scale_recommendation_id=uuid.UUID(scale_dict["id"]) if scale_dict.get("id") else None,
        )
        db.add(lc)
    await db.flush()
    return {"candidates_created": len(candidates)}


# ---------------------------------------------------------------------------
# WRITE: Scale Blockers
# ---------------------------------------------------------------------------

async def recompute_scale_blockers(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand, accounts, acc_dicts, offers, scale_rec, scale_dict, trust_avg, leak_count, cann_risk, aud_sep = await _brand_context(db, brand_id)
    await db.execute(delete(ScaleBlockerReport).where(ScaleBlockerReport.brand_id == brand_id, ScaleBlockerReport.is_resolved.is_(False)))

    readiness = float(scale_dict.get("scale_readiness_score", 0)) if scale_dict else 0
    exp_conf = float(scale_rec.expansion_confidence if scale_rec else 0.3)
    n = max(1, len(acc_dicts))
    avg_ctr = sum(float(a.get("ctr", 0)) for a in acc_dicts) / n
    avg_cvr = sum(float(a.get("conversion_rate", 0)) for a in acc_dicts) / n
    total_cap = sum(int(a.get("posting_capacity_per_day") or 0) for a in acc_dicts)
    blockers = diagnose_scale_blockers(
        readiness, acc_dicts, trust_avg, leak_count, cann_risk, aud_sep, len(offers),
        expansion_confidence=exp_conf,
        avg_ctr=avg_ctr,
        avg_cvr=avg_cvr,
        total_posting_cap=total_cap,
        monetization_depth=len(offers),
    )
    for b in blockers:
        db.add(ScaleBlockerReport(
            brand_id=brand_id, blocker_type=b["blocker_type"], severity=b["severity"],
            title=b["title"], explanation=b.get("explanation"),
            recommended_fix=b.get("recommended_fix"),
            current_value=b["current_value"], threshold_value=b["threshold_value"],
            evidence=b.get("evidence"),
        ))
    await db.flush()
    return {"blockers_found": len(blockers)}


# ---------------------------------------------------------------------------
# WRITE: Launch Readiness
# ---------------------------------------------------------------------------

async def recompute_launch_readiness(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand, accounts, acc_dicts, offers, scale_rec, scale_dict, trust_avg, leak_count, cann_risk, aud_sep = await _brand_context(db, brand_id)
    await db.execute(delete(LaunchReadinessReport).where(LaunchReadinessReport.brand_id == brand_id))

    readiness = float(scale_dict.get("scale_readiness_score", 0)) if scale_dict else 0
    exp_conf = float(scale_rec.expansion_confidence if scale_rec else 0.3)
    avg_sat = sum(float(a.saturation_score or 0) for a in accounts) / max(1, len(accounts))
    total_cap = sum(a.posting_capacity_per_day or 0 for a in accounts)
    funnel_cvr = sum(float(a.conversion_rate or 0) for a in accounts) / max(1, len(accounts))

    result = compute_launch_readiness(
        readiness, exp_conf, aud_sep, avg_sat, len(offers), funnel_cvr,
        trust_avg, int(total_cap), cann_risk,
    )
    db.add(LaunchReadinessReport(
        brand_id=brand_id, launch_readiness_score=result["launch_readiness_score"],
        explanation=result["explanation"], recommended_action=result["recommended_action"],
        gating_factors=result["gating_factors"], components=result["components"],
    ))
    await db.flush()
    return {"readiness_score": result["launch_readiness_score"], "action": result["recommended_action"]}


# ---------------------------------------------------------------------------
# WRITE: Acknowledge / Resolve
# ---------------------------------------------------------------------------

async def acknowledge_alert(
    db: AsyncSession, alert_id: uuid.UUID, organization_id: uuid.UUID
) -> Tuple[Optional[OperatorAlert], Optional[AccessError]]:
    alert = await db.get(OperatorAlert, alert_id)
    if not alert:
        return None, "not_found"
    brand = await db.get(Brand, alert.brand_id)
    if not brand or brand.organization_id != organization_id:
        return None, "forbidden"
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
    await db.flush()
    return alert, None


async def resolve_alert(
    db: AsyncSession, alert_id: uuid.UUID, organization_id: uuid.UUID, notes: Optional[str] = None
) -> Tuple[Optional[OperatorAlert], Optional[AccessError]]:
    alert = await db.get(OperatorAlert, alert_id)
    if not alert:
        return None, "not_found"
    brand = await db.get(Brand, alert.brand_id)
    if not brand or brand.organization_id != organization_id:
        return None, "forbidden"
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc).isoformat()
    alert.resolution_notes = notes
    await db.flush()
    return alert, None


# ---------------------------------------------------------------------------
# READ: All side-effect free
# ---------------------------------------------------------------------------

async def get_alerts(
    db: AsyncSession,
    brand_id: uuid.UUID,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
) -> list[dict]:
    rows = list((await db.execute(
        select(OperatorAlert).where(OperatorAlert.brand_id == brand_id, OperatorAlert.is_active.is_(True))
        .order_by(OperatorAlert.urgency.desc())
    )).scalars().all())
    out = [_ser_alert(a) for a in rows]
    if status:
        out = [x for x in out if x.get("status") == status]
    if alert_type:
        out = [x for x in out if x.get("alert_type") == alert_type]
    if severity:
        out = [x for x in out if (x.get("supporting_metrics") or {}).get("severity") == severity]
    return out


async def get_launch_candidates(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(LaunchCandidate).where(LaunchCandidate.brand_id == brand_id, LaunchCandidate.is_active.is_(True))
        .order_by(LaunchCandidate.urgency.desc())
    )).scalars().all())
    return [_ser_candidate(c) for c in rows]


async def get_launch_candidate_detail(
    db: AsyncSession, candidate_id: uuid.UUID, organization_id: uuid.UUID
) -> Tuple[Optional[dict], Optional[AccessError]]:
    c = await db.get(LaunchCandidate, candidate_id)
    if not c:
        return None, "not_found"
    brand = await db.get(Brand, c.brand_id)
    if not brand or brand.organization_id != organization_id:
        return None, "forbidden"
    return _ser_candidate(c), None


async def get_scale_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(ScaleBlockerReport).where(ScaleBlockerReport.brand_id == brand_id, ScaleBlockerReport.is_resolved.is_(False))
    )).scalars().all())
    return [{
        "id": str(b.id), "blocker_type": b.blocker_type, "severity": b.severity,
        "title": b.title, "explanation": b.explanation, "recommended_fix": b.recommended_fix,
        "current_value": b.current_value, "threshold_value": b.threshold_value,
    } for b in rows]


async def get_launch_readiness(db: AsyncSession, brand_id: uuid.UUID) -> Optional[dict]:
    r = (await db.execute(
        select(LaunchReadinessReport).where(LaunchReadinessReport.brand_id == brand_id, LaunchReadinessReport.is_active.is_(True))
        .order_by(LaunchReadinessReport.created_at.desc()).limit(1)
    )).scalars().first()
    if not r:
        return None
    return {
        "id": str(r.id), "launch_readiness_score": r.launch_readiness_score,
        "explanation": r.explanation, "recommended_action": r.recommended_action,
        "gating_factors": r.gating_factors, "components": r.components,
    }


async def get_notifications(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(NotificationDelivery).where(NotificationDelivery.brand_id == brand_id)
        .order_by(NotificationDelivery.created_at.desc()).limit(50)
    )).scalars().all())
    return [{
        "id": str(n.id), "alert_id": str(n.alert_id) if n.alert_id else None,
        "channel": n.channel, "status": n.status, "attempts": n.attempts,
        "last_error": n.last_error, "delivered_at": n.delivered_at,
    } for n in rows]


# Serializers
def _ser_alert(a: OperatorAlert) -> dict:
    sm = a.supporting_metrics or {}
    return {
        "id": str(a.id), "alert_type": a.alert_type, "title": a.title,
        "summary": a.summary, "explanation": a.explanation,
        "recommended_action": a.recommended_action,
        "confidence": a.confidence, "urgency": a.urgency,
        "expected_upside": a.expected_upside, "expected_cost": a.expected_cost,
        "expected_time_to_signal_days": a.expected_time_to_signal_days,
        "supporting_metrics": a.supporting_metrics,
        "blocking_factors": a.blocking_factors,
        "severity": sm.get("severity"),
        "dashboard_section": sm.get("dashboard_section"),
        "linked_scale_recommendation_id": str(a.linked_scale_recommendation_id) if a.linked_scale_recommendation_id else None,
        "linked_launch_candidate_id": str(a.linked_launch_candidate_id) if a.linked_launch_candidate_id else None,
        "status": a.status, "acknowledged_at": a.acknowledged_at, "resolved_at": a.resolved_at,
        "created_at": str(a.created_at),
    }


def _ser_candidate(c: LaunchCandidate) -> dict:
    return {
        "id": str(c.id), "candidate_type": c.candidate_type,
        "primary_platform": c.primary_platform, "secondary_platform": c.secondary_platform,
        "niche": c.niche, "sub_niche": c.sub_niche,
        "language": c.language, "geography": c.geography,
        "avatar_persona_strategy": c.avatar_persona_strategy,
        "monetization_path": c.monetization_path,
        "content_style": c.content_style, "posting_strategy": c.posting_strategy,
        "expected_monthly_revenue_min": c.expected_monthly_revenue_min,
        "expected_monthly_revenue_max": c.expected_monthly_revenue_max,
        "expected_launch_cost": c.expected_launch_cost,
        "expected_time_to_signal_days": c.expected_time_to_signal_days,
        "expected_time_to_profit_days": c.expected_time_to_profit_days,
        "cannibalization_risk": c.cannibalization_risk,
        "audience_separation_score": c.audience_separation_score,
        "confidence": c.confidence, "urgency": c.urgency,
        "supporting_reasons": c.supporting_reasons,
        "required_resources": c.required_resources,
        "launch_blockers": c.launch_blockers,
        "linked_scale_recommendation_id": str(c.linked_scale_recommendation_id) if c.linked_scale_recommendation_id else None,
    }
