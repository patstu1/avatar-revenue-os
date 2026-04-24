"""Quality Governor Service — score content, persist, block, improve."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.quality_governor import (
    QualityBlock,
    QualityDimensionScore,
    QualityGovernorReport,
    QualityImprovementAction,
)
from packages.scoring.quality_governor_engine import DIMENSIONS, score_content


async def score_content_item(
    db: AsyncSession, brand_id: uuid.UUID, content_item_id: uuid.UUID,
) -> dict[str, Any]:
    ci = (await db.execute(select(ContentItem).where(ContentItem.id == content_item_id))).scalar_one_or_none()
    if not ci:
        return {"status": "not_found"}

    (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    ctx = await _build_context(db, brand_id, ci)

    ct = ci.content_type
    content_dict = {
        "title": ci.title or "",
        "hook_text": ci.title or "",
        "body_text": ci.description or "",
        "cta_text": getattr(ci, "cta_type", None) or "",
        "cta_type": getattr(ci, "cta_type", None),
        "offer_id": str(ci.offer_id) if ci.offer_id else None,
        "monetization_method": ci.monetization_method,
        "platform": ci.platform or "",
        "content_type": ct.value if hasattr(ct, "value") else str(ct),
    }

    result = score_content(content_dict, ctx)

    await db.execute(delete(QualityImprovementAction).where(
        QualityImprovementAction.report_id.in_(
            select(QualityGovernorReport.id).where(QualityGovernorReport.content_item_id == content_item_id)
        )
    ))
    await db.execute(delete(QualityDimensionScore).where(
        QualityDimensionScore.report_id.in_(
            select(QualityGovernorReport.id).where(QualityGovernorReport.content_item_id == content_item_id)
        )
    ))
    await db.execute(delete(QualityBlock).where(QualityBlock.content_item_id == content_item_id))
    await db.execute(delete(QualityGovernorReport).where(QualityGovernorReport.content_item_id == content_item_id))

    report = QualityGovernorReport(
        brand_id=brand_id,
        content_item_id=content_item_id,
        total_score=result["total_score"],
        verdict=result["verdict"],
        publish_allowed=result["publish_allowed"],
        confidence=result["confidence"],
        reasons=result["reasons"],
    )
    db.add(report)
    await db.flush()

    for d in DIMENSIONS:
        dim_data = result["dimensions"].get(d, {})
        db.add(QualityDimensionScore(
            report_id=report.id,
            dimension=d,
            score=dim_data.get("score", 0),
            max_score=1.0,
            explanation=dim_data.get("explanation"),
        ))

    for block in result["blocks"]:
        db.add(QualityBlock(
            brand_id=brand_id,
            content_item_id=content_item_id,
            report_id=report.id,
            block_reason=f"{block['dimension']}: {block['reason']}",
            severity="hard",
        ))

    for imp in result["improvements"]:
        db.add(QualityImprovementAction(
            report_id=report.id,
            dimension=imp["dimension"],
            action=imp["action"],
            priority=imp["priority"],
        ))

    if not result["publish_allowed"]:
        ci.status = "quality_blocked"

    await db.flush()
    return result


async def recompute_brand_quality(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict[str, Any]:
    items = list((await db.execute(
        select(ContentItem).where(
            ContentItem.brand_id == brand_id,
            ContentItem.status.in_(("draft", "script_generated", "media_complete", "approved")),
        ).limit(100)
    )).scalars().all())

    processed = 0
    for ci in items:
        await score_content_item(db, brand_id, ci.id)
        processed += 1

    return {"rows_processed": processed, "status": "completed"}


async def _build_context(db: AsyncSession, brand_id: uuid.UUID, ci: ContentItem) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()

    recent_titles = list((await db.execute(
        select(ContentItem.title).where(ContentItem.brand_id == brand_id).order_by(ContentItem.created_at.desc()).limit(20)
    )).scalars().all())

    existing_hashes = []
    recent_bodies = list((await db.execute(
        select(ContentItem.description).where(ContentItem.brand_id == brand_id, ContentItem.id != ci.id).limit(50)
    )).scalars().all())
    for body in recent_bodies:
        if body:
            existing_hashes.append(hashlib.sha256(body.encode()).hexdigest()[:16])

    fatigue = 0.0
    recent_count = 0
    if ci.creator_account_id:
        acct = (await db.execute(select(CreatorAccount).where(CreatorAccount.id == ci.creator_account_id))).scalar_one_or_none()
        if acct:
            fatigue = float(acct.fatigue_score or 0)
            health_val = acct.account_health.value if hasattr(acct.account_health, "value") else str(acct.account_health)
        else:
            health_val = "healthy"
        recent_count = (await db.execute(
            select(func.count()).select_from(ContentItem).where(ContentItem.creator_account_id == ci.creator_account_id)
        )).scalar() or 0
    else:
        health_val = "healthy"

    offer_cvr = 0.0
    if ci.offer_id:
        offer = (await db.execute(select(Offer).where(Offer.id == ci.offer_id))).scalar_one_or_none()
        if offer:
            offer_cvr = float(offer.conversion_rate or 0)

    return {
        "recent_titles": [t for t in recent_titles if t],
        "existing_content_hashes": existing_hashes,
        "fatigue_score": fatigue,
        "recent_post_count": recent_count,
        "account_health": health_val,
        "offer_conversion_rate": offer_cvr,
        "niche": brand.niche if brand else "",
        "tone_of_voice": brand.tone_of_voice if brand else "",
    }


async def list_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(QualityGovernorReport).where(QualityGovernorReport.brand_id == brand_id, QualityGovernorReport.is_active.is_(True)).order_by(QualityGovernorReport.total_score)
    )).scalars().all())


async def list_blocks(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(QualityBlock).where(QualityBlock.brand_id == brand_id, QualityBlock.is_active.is_(True))
    )).scalars().all())


async def get_publish_eligibility(db: AsyncSession, content_item_id: uuid.UUID) -> dict[str, Any]:
    """Downstream query: is this content item allowed to publish?"""
    report = (await db.execute(
        select(QualityGovernorReport).where(QualityGovernorReport.content_item_id == content_item_id, QualityGovernorReport.is_active.is_(True)).order_by(QualityGovernorReport.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not report:
        return {"publish_allowed": True, "verdict": "unscored", "total_score": 0}
    return {"publish_allowed": report.publish_allowed, "verdict": report.verdict, "total_score": report.total_score}
