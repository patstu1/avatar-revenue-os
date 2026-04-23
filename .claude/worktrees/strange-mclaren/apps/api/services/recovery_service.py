"""Recovery service — detect operational incidents and persist recommended actions."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import JobStatus
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.offers import LtvModel, SponsorOpportunity
from packages.db.models.portfolio import PaidAmplificationJob
from packages.db.models.publishing import PerformanceMetric, PublishJob
from packages.db.models.recovery import RecoveryAction, RecoveryIncident
from packages.db.models.system import ProviderUsageCost, SystemJob
from packages.scoring.recovery_engine import (
    RECOVERY,
    detect_recovery_incidents,
    recommend_recovery_actions,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != RECOVERY}


def _escalation_state(severity: str) -> str:
    return {
        "critical": "escalated",
        "high": "pending_operator",
        "medium": "monitoring",
        "low": "monitoring",
    }.get(severity, "open")


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_recovery_incidents(
    db: AsyncSession, brand_id: uuid.UUID
) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    account_count = (
        await db.execute(
            select(func.count(CreatorAccount.id)).where(CreatorAccount.brand_id == brand_id)
        )
    ).scalar() or 0

    failed_jobs = (
        await db.execute(
            select(func.count(SystemJob.id)).where(
                SystemJob.brand_id == brand_id,
                SystemJob.status == JobStatus.FAILED,
            )
        )
    ).scalar() or 0

    total_jobs = (
        await db.execute(
            select(func.count(SystemJob.id)).where(SystemJob.brand_id == brand_id)
        )
    ).scalar() or 1

    publish_failure_rate = failed_jobs / max(total_jobs, 1)

    avg_engagement = (
        await db.execute(
            select(func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.04)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_engagement = float(avg_engagement or 0.04)

    avg_ctr = (
        await db.execute(
            select(func.coalesce(func.avg(PerformanceMetric.ctr), 0.04)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_ctr = float(avg_ctr or 0.04)

    avg_revenue = (
        await db.execute(
            select(func.coalesce(func.avg(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).scalar()
    avg_revenue = float(avg_revenue or 0.0)

    pending_jobs = (
        await db.execute(
            select(func.count(SystemJob.id)).where(
                SystemJob.brand_id == brand_id,
                SystemJob.status == JobStatus.PENDING,
            )
        )
    ).scalar() or 0

    provider_jobs = (
        await db.execute(
            select(func.count(SystemJob.id)).where(
                SystemJob.brand_id == brand_id,
                or_(
                    SystemJob.job_name.ilike("%provider%"),
                    SystemJob.job_type.ilike("%provider%"),
                ),
            )
        )
    ).scalar() or 0

    provider_failed = (
        await db.execute(
            select(func.count(SystemJob.id)).where(
                SystemJob.brand_id == brand_id,
                SystemJob.status == JobStatus.FAILED,
                or_(
                    SystemJob.job_name.ilike("%provider%"),
                    SystemJob.job_type.ilike("%provider%"),
                ),
            )
        )
    ).scalar() or 0

    total_cost = (
        await db.execute(
            select(func.coalesce(func.sum(ProviderUsageCost.cost), 0.0)).where(
                ProviderUsageCost.brand_id == brand_id
            )
        )
    ).scalar()
    total_cost = float(total_cost or 0.0)

    paid_spent = (
        await db.execute(
            select(func.coalesce(func.sum(PaidAmplificationJob.spent), 0.0)).where(
                PaidAmplificationJob.brand_id == brand_id
            )
        )
    ).scalar()
    paid_spent = float(paid_spent or 0.0)

    publish_rows = (
        await db.execute(
            select(func.count(PublishJob.id)).where(PublishJob.brand_id == brand_id)
        )
    ).scalar() or 0
    publish_failed = (
        await db.execute(
            select(func.count(PublishJob.id)).where(
                PublishJob.brand_id == brand_id,
                PublishJob.status == JobStatus.FAILED,
            )
        )
    ).scalar() or 0
    landing_fail_rate = publish_failed / max(publish_rows, 1)

    ltv_rows = list(
        (
            await db.execute(select(LtvModel).where(LtvModel.brand_id == brand_id))
        )
        .scalars()
        .all()
    )
    ltv_vals = [float(m.estimated_ltv_90d) for m in ltv_rows if m.estimated_ltv_90d]
    ltv_drop_metric = 0.0
    if len(ltv_vals) >= 2:
        hi = max(ltv_vals)
        lo = min(ltv_vals)
        if hi > 0:
            ltv_drop_metric = (lo - hi) / hi

    sponsor_rows = list(
        (
            await db.execute(
                select(SponsorOpportunity).where(SponsorOpportunity.brand_id == brand_id)
            )
        )
        .scalars()
        .all()
    )
    sponsor_roi_change = 0.0
    if sponsor_rows:
        deals = [float(s.deal_value) for s in sponsor_rows]
        avg_deal = sum(deals) / len(deals)
        sponsor_roi_change = (avg_deal - 15000.0) / max(15000.0, 1.0)

    bounce_rows = (
        await db.execute(
            select(PerformanceMetric.raw_data).where(PerformanceMetric.brand_id == brand_id)
        )
    ).all()
    email_bounce_rate = 0.0
    for (raw,) in bounce_rows:
        if isinstance(raw, dict) and "email_bounce_rate" in raw:
            email_bounce_rate = max(email_bounce_rate, float(raw.get("email_bounce_rate", 0)))

    system_state: dict[str, Any] = {}

    if publish_failure_rate > 0.05:
        system_state["publishing_failure_spike"] = {
            "metric_value": publish_failure_rate,
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if provider_jobs > 0 and provider_failed / max(provider_jobs, 1) > 0.12:
        system_state["provider_outage"] = {
            "metric_value": provider_failed / max(provider_jobs, 1),
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    baseline_ctr = 0.06
    if avg_ctr < baseline_ctr * 0.55:
        conv_metric = (avg_ctr - baseline_ctr) / baseline_ctr
        system_state["conversion_decline"] = {
            "metric_value": conv_metric,
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if avg_engagement < 0.02:
        fatigue_score = 1.0 - (avg_engagement / 0.04)
        system_state["fatigue_rise"] = {
            "metric_value": max(0.0, fatigue_score),
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if pending_jobs > 30:
        system_state["queue_backlog"] = {
            "metric_value": float(pending_jobs),
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if account_count > 0:
        risk_per_account = min(1.0, failed_jobs / max(account_count, 1))
        if risk_per_account > 0.3:
            system_state["account_warning"] = {
                "metric_value": risk_per_account,
                "scope_type": "brand",
                "scope_id": str(brand_id),
            }

    if ltv_drop_metric <= -0.08:
        system_state["ltv_drop"] = {
            "metric_value": ltv_drop_metric,
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if paid_spent > 0 and avg_revenue >= 0:
        cac_ratio = paid_spent / max(avg_revenue * 10.0, 1.0)
        if cac_ratio > 0.25:
            system_state["cac_spike"] = {
                "metric_value": min(1.0, cac_ratio),
                "scope_type": "brand",
                "scope_id": str(brand_id),
            }

    if sponsor_rows and sponsor_roi_change <= -0.15:
        system_state["sponsor_underperformance"] = {
            "metric_value": sponsor_roi_change,
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if landing_fail_rate > 0.2 or (publish_rows > 3 and avg_ctr < 0.008):
        system_state["landing_page_failure"] = {
            "metric_value": min(0.02, avg_ctr) if publish_rows > 3 else landing_fail_rate,
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if email_bounce_rate > 0.03:
        system_state["email_deliverability_issue"] = {
            "metric_value": email_bounce_rate,
            "scope_type": "brand",
            "scope_id": str(brand_id),
        }

    if total_cost > 0 and avg_revenue > 0:
        cost_change = total_cost / max(avg_revenue * 50.0, 1.0)
        if cost_change > 0.15:
            system_state["cost_spike"] = {
                "metric_value": min(1.0, cost_change),
                "scope_type": "brand",
                "scope_id": str(brand_id),
            }

    incidents = detect_recovery_incidents(system_state, {})

    if not incidents:
        return {"incidents": 0, "actions": 0}

    await db.execute(delete(RecoveryAction).where(RecoveryAction.brand_id == brand_id))
    await db.execute(delete(RecoveryIncident).where(RecoveryIncident.brand_id == brand_id))

    incident_count = 0
    action_count = 0
    now = datetime.now(timezone.utc)

    incident_models: list[RecoveryIncident] = []
    for item in incidents:
        r = _strip_meta(item)
        scope_id_raw = r.get("scope_id")
        try:
            scope_uuid = uuid.UUID(str(scope_id_raw)) if scope_id_raw else None
        except (ValueError, AttributeError, TypeError):
            scope_uuid = None

        sev = r.get("severity", "low")
        expl = {
            "explanation": r.get("explanation", ""),
            "confidence": r.get("confidence", 0),
            "failure_type": r.get("incident_type"),
        }

        incident_model = RecoveryIncident(
            brand_id=brand_id,
            incident_type=r.get("incident_type", "unknown"),
            severity=sev,
            scope_type=r.get("scope_type", "brand"),
            scope_id=scope_uuid,
            detected_at=now,
            status="open",
            explanation_json=expl,
            is_active=True,
            escalation_state=_escalation_state(sev),
            recommended_recovery_action=None,
            automatic_action_taken=None,
        )
        db.add(incident_model)
        incident_models.append(incident_model)
        incident_count += 1

    await db.flush()

    actions = recommend_recovery_actions(incidents, {})

    incident_type_map: dict[str, RecoveryIncident] = {}
    for im in incident_models:
        incident_type_map[im.incident_type] = im

    primary_by_type: dict[str, str] = {}
    for item in actions:
        a = _strip_meta(item)
        itype = a.get("incident_type", "unknown")
        if itype not in primary_by_type:
            primary_by_type[itype] = a.get("action_type", "notify_operator")

    for im in incident_models:
        im.recommended_recovery_action = primary_by_type.get(im.incident_type)

    for item in actions:
        a = _strip_meta(item)
        incident_type = a.get("incident_type", "unknown")
        parent_incident = incident_type_map.get(incident_type)
        if not parent_incident:
            continue

        mode = a.get("action_mode", "manual")

        db.add(
            RecoveryAction(
                brand_id=brand_id,
                incident_id=parent_incident.id,
                action_type=a.get("action_type", "notify_operator"),
                action_mode=mode,
                executed=False,
                expected_effect_json=a.get("expected_effect", {}),
                result_json=None,
                confidence_score=float(a.get("confidence", 0)),
            )
        )
        action_count += 1

    await db.flush()
    return {"incidents": incident_count, "actions": action_count}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _ri_dict(x: RecoveryIncident) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "incident_type": x.incident_type,
        "severity": x.severity,
        "scope_type": x.scope_type,
        "scope_id": str(x.scope_id) if x.scope_id else None,
        "detected_at": x.detected_at,
        "status": x.status,
        "explanation_json": x.explanation_json,
        "is_active": x.is_active,
        "escalation_state": x.escalation_state,
        "recommended_recovery_action": x.recommended_recovery_action,
        "automatic_action_taken": x.automatic_action_taken,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _ra_dict(x: RecoveryAction) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "incident_id": str(x.incident_id),
        "action_type": x.action_type,
        "action_mode": x.action_mode,
        "executed": x.executed,
        "expected_effect_json": x.expected_effect_json,
        "result_json": x.result_json,
        "confidence_score": x.confidence_score,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


async def get_recovery_incidents(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    sev_rank = case(
        (RecoveryIncident.severity == "critical", 0),
        (RecoveryIncident.severity == "high", 1),
        (RecoveryIncident.severity == "medium", 2),
        (RecoveryIncident.severity == "low", 3),
        else_=4,
    )
    rows = list(
        (
            await db.execute(
                select(RecoveryIncident)
                .where(
                    RecoveryIncident.brand_id == brand_id,
                    RecoveryIncident.is_active.is_(True),
                )
                .order_by(sev_rank, RecoveryIncident.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return []

    actions = list(
        (
            await db.execute(
                select(RecoveryAction)
                .where(RecoveryAction.brand_id == brand_id)
                .order_by(RecoveryAction.created_at.asc())
                .limit(500)
            )
        )
        .scalars()
        .all()
    )
    by_incident: dict[uuid.UUID, list[RecoveryAction]] = defaultdict(list)
    for a in actions:
        by_incident[a.incident_id].append(a)

    out: list[dict[str, Any]] = []
    for r in rows:
        d = _ri_dict(r)
        d["actions"] = [_ra_dict(x) for x in by_incident.get(r.id, [])]
        expl = d.get("explanation_json") or {}
        d["confidence"] = expl.get("confidence")
        d["expected_mitigation_effect"] = (
            d["actions"][0].get("expected_effect_json") if d["actions"] else None
        )
        out.append(d)
    return out


async def get_recovery_actions(
    db: AsyncSession, brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(RecoveryAction)
                .where(RecoveryAction.brand_id == brand_id)
                .order_by(RecoveryAction.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_ra_dict(r) for r in rows]
