"""Failure-Family Suppression Service — detect, suppress, persist, decay."""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.content import ContentItem
from packages.db.models.failure_family import (
    FailureFamilyMember,
    FailureFamilyReport,
    SuppressionEvent,
    SuppressionRule,
)
from packages.db.models.pattern_memory import LosingPatternMemory
from packages.db.models.quality_governor import QualityGovernorReport
from packages.scoring.failure_family_engine import (
    build_suppression_rules,
    check_suppression_decay,
    cluster_failures,
    detect_repeat_failures,
)


async def recompute_failure_families(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict[str, Any]:
    await db.execute(delete(SuppressionEvent).where(SuppressionEvent.brand_id == brand_id))
    await db.execute(delete(SuppressionRule).where(SuppressionRule.brand_id == brand_id))
    await db.execute(delete(FailureFamilyMember).where(
        FailureFamilyMember.report_id.in_(select(FailureFamilyReport.id).where(FailureFamilyReport.brand_id == brand_id))
    ))
    await db.execute(delete(FailureFamilyReport).where(FailureFamilyReport.brand_id == brand_id))

    failing_items = await _gather_failing_items(db, brand_id)
    families = cluster_failures(failing_items)
    repeats = detect_repeat_failures(families)
    rules = build_suppression_rules(repeats)

    for f in families:
        report = FailureFamilyReport(
            brand_id=brand_id, family_type=f["family_type"], family_key=f["family_key"],
            failure_count=f["failure_count"], avg_fail_score=f["avg_fail_score"],
            first_seen_at=f.get("first_seen_at"), last_seen_at=f.get("last_seen_at"),
            recommended_alternative=next((r.get("recommended_alternative") for r in rules if r["family_key"] == f["family_key"]), None),
            explanation=f"{f['family_type']}:{f['family_key']} — {f['failure_count']} failures, avg {f['avg_fail_score']:.2f}",
        )
        db.add(report)
        await db.flush()

        for m in f.get("members", [])[:20]:
            ci_id = None
            if m.get("content_item_id"):
                try:
                    ci_id = uuid.UUID(str(m["content_item_id"]))
                except (ValueError, TypeError):
                    logger.debug("failure_member_content_id_parse_failed", exc_info=True)
            db.add(FailureFamilyMember(
                report_id=report.id, content_item_id=ci_id,
                fail_score=float(m.get("fail_score", 0)), detail=m.get("detail"),
            ))

        matching_rules = [r for r in rules if r["family_key"] == f["family_key"]]
        for r in matching_rules:
            db.add(SuppressionRule(
                brand_id=brand_id, report_id=report.id,
                family_type=r["family_type"], family_key=r["family_key"],
                suppression_mode=r["suppression_mode"], retest_after_days=r["retest_after_days"],
                expires_at=r["expires_at"], reason=r["reason"],
            ))

    await db.flush()
    return {"rows_processed": len(families), "suppressed": len(rules), "status": "completed"}


async def _gather_failing_items(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    losers = list((await db.execute(
        select(LosingPatternMemory).where(LosingPatternMemory.brand_id == brand_id, LosingPatternMemory.is_active.is_(True))
    )).scalars().all())
    for lp in losers:
        items.append({
            "content_item_id": None, "pattern_id": str(lp.id),
            "fail_score": float(lp.fail_score), "family_type_val": lp.pattern_type,
            lp.pattern_type: lp.pattern_name, "created_at": lp.created_at,
            "detail": f"Losing pattern: {lp.pattern_type}:{lp.pattern_name}",
            "hook_type": lp.pattern_name if lp.pattern_type == "hook" else None,
            "content_form": lp.pattern_name if lp.pattern_type == "content_form" else None,
            "offer_angle": lp.pattern_name if lp.pattern_type == "offer_angle" else None,
            "cta_style": lp.pattern_name if lp.pattern_type == "cta" else None,
            "creative_structure": lp.pattern_name if lp.pattern_type == "creative_structure" else None,
            "monetization_path": lp.pattern_name if lp.pattern_type == "monetization" else None,
        })

    qg_fails = list((await db.execute(
        select(QualityGovernorReport).where(
            QualityGovernorReport.brand_id == brand_id,
            QualityGovernorReport.verdict == "fail",
            QualityGovernorReport.is_active.is_(True),
        ).limit(100)
    )).scalars().all())
    for qg in qg_fails:
        ci = (await db.execute(select(ContentItem).where(ContentItem.id == qg.content_item_id))).scalar_one_or_none()
        if ci:
            ct = ci.content_type
            ct_val = ct.value if hasattr(ct, "value") else str(ct)
            items.append({
                "content_item_id": str(ci.id), "fail_score": 1.0 - qg.total_score,
                "created_at": qg.created_at, "detail": f"Quality fail: {qg.total_score:.2f}",
                "hook_type": getattr(ci, "hook_type", None),
                "content_form": ct_val,
                "offer_angle": getattr(ci, "offer_angle", None),
                "cta_style": getattr(ci, "cta_type", None),
                "creative_structure": getattr(ci, "creative_structure", None),
                "monetization_path": ci.monetization_method,
            })

    return items


async def run_decay_check(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    active_rules = list((await db.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand_id, SuppressionRule.is_active.is_(True))
    )).scalars().all())

    rule_dicts = [{"family_type": r.family_type, "family_key": r.family_key, "expires_at": r.expires_at, "is_active": r.is_active} for r in active_rules]
    expired = check_suppression_decay(rule_dicts)

    deactivated = 0
    for exp in expired:
        for r in active_rules:
            if r.family_type == exp["family_type"] and r.family_key == exp["family_key"]:
                r.is_active = False
                deactivated += 1

    return {"expired": deactivated, "active_remaining": len(active_rules) - deactivated, "status": "completed"}


async def list_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(FailureFamilyReport).where(FailureFamilyReport.brand_id == brand_id, FailureFamilyReport.is_active.is_(True)).order_by(FailureFamilyReport.failure_count.desc())
    )).scalars().all())


async def list_suppression_rules(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand_id, SuppressionRule.is_active.is_(True))
    )).scalars().all())


async def list_suppression_events(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(SuppressionEvent).where(SuppressionEvent.brand_id == brand_id, SuppressionEvent.is_active.is_(True)).limit(50)
    )).scalars().all())


async def get_active_suppressions_for_downstream(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Downstream: return active suppression rules for content/form/experiment blocking."""
    rules = list((await db.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand_id, SuppressionRule.is_active.is_(True))
    )).scalars().all())
    return [{"family_type": r.family_type, "family_key": r.family_key, "mode": r.suppression_mode, "reason": r.reason} for r in rules]
