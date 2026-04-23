"""Content Form Selection service — recompute + read."""
from __future__ import annotations

import os
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.content_form import (
    ContentFormBlocker,
    ContentFormMixReport,
    ContentFormRecommendation,
)
from packages.db.models.core import Brand
from packages.db.enums import MonetizationMethod
from packages.db.models.offers import Offer
from packages.db.models.pattern_memory import WinningPatternMemory
from packages.scoring.content_form_engine import (
    compute_mix_reports,
    detect_content_form_blockers,
    recommend_content_forms,
)

_ENGINE_MONETIZATION = {
    "affiliate": "affiliate",
    "adsense": "ads",
    "sponsor": "sponsorship",
    "product": "digital_product",
    "course": "digital_product",
    "membership": "membership",
    "consulting": "coaching",
    "lead_gen": "affiliate",
}


def _monetization_for_engine(offers: list) -> str:
    if not offers:
        return "affiliate"
    m = offers[0].monetization_method
    key = m.value if isinstance(m, MonetizationMethod) else str(m)
    return _ENGINE_MONETIZATION.get(key, "affiliate")


async def recompute_recommendations(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    accounts = list((await db.execute(
        select(CreatorAccount).where(
            CreatorAccount.brand_id == brand_id,
            CreatorAccount.is_active.is_(True),
        )
    )).scalars().all())

    offers = list((await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all())

    has_avatar = bool(os.getenv("TAVUS_API_KEY") or os.getenv("HEYGEN_API_KEY"))
    has_voice = bool(os.getenv("ELEVENLABS_API_KEY"))
    monetization = _monetization_for_engine(offers)

    all_recs: list[dict[str, Any]] = []
    for acct in accounts:
        platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
        recs = recommend_content_forms(
            platform=platform,
            monetization=monetization,
            funnel_stage="awareness",
            saturation=float(acct.saturation_score or 0),
            fatigue=float(acct.fatigue_score or 0),
            has_avatar=has_avatar,
            has_voice=has_voice,
            account_maturity="mature" if float(acct.total_revenue or 0) > 500 else "new",
            trust_need="low",
            niche=brand.niche or "general",
            account_id=str(acct.id),
        )
        all_recs.extend(recs)

    await db.execute(delete(ContentFormRecommendation).where(ContentFormRecommendation.brand_id == brand_id))

    for rec in all_recs:
        row = dict(rec)
        acct_id = row.pop("account_id", None)
        db.add(ContentFormRecommendation(
            brand_id=brand_id,
            account_id=uuid.UUID(acct_id) if acct_id else None,
            **row,
        ))

    await db.flush()

    # Pattern memory boost
    wp_rows = list((await db.execute(
        select(WinningPatternMemory).where(
            WinningPatternMemory.brand_id == brand_id,
            WinningPatternMemory.is_active.is_(True),
            WinningPatternMemory.content_form.isnot(None),
        )
    )).scalars().all())
    form_max_win: dict[str, float] = {}
    for wp in wp_rows:
        cf = wp.content_form
        if cf:
            form_max_win[cf] = max(form_max_win.get(cf, 0.0), float(wp.win_score or 0.0))
    rec_rows = list((await db.execute(
        select(ContentFormRecommendation).where(ContentFormRecommendation.brand_id == brand_id)
    )).scalars().all())
    boost_factor = 0.02
    for rec in rec_rows:
        max_win = form_max_win.get(rec.recommended_content_form)
        if max_win is not None:
            rec.confidence = float(rec.confidence or 0.0) + min(0.2, max_win * boost_factor)

    # Promote-winner rule boost
    from packages.db.models.promote_winner import PromotedWinnerRule
    promo_rows = list((await db.execute(
        select(PromotedWinnerRule).where(
            PromotedWinnerRule.brand_id == brand_id,
            PromotedWinnerRule.is_active.is_(True),
            PromotedWinnerRule.rule_type == "default_content_form",
        )
    )).scalars().all())
    for promo in promo_rows:
        for rec in rec_rows:
            if rec.recommended_content_form == promo.rule_key:
                rec.confidence = float(rec.confidence or 0.0) + float(promo.weight_boost or 0.0)

    # Account-state content form filtering
    from packages.db.models.account_state_intel import AccountStateReport
    state_rows = list((await db.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True))
    )).scalars().all())
    if state_rows:
        allowed_forms: set[str] = set()
        for sr in state_rows:
            for f in (sr.suitable_content_forms or []):
                allowed_forms.add(f)
        if allowed_forms:
            for rec in rec_rows:
                if rec.recommended_content_form not in allowed_forms:
                    rec.confidence = max(0.0, float(rec.confidence or 0) - 0.3)

    # Failure-family suppression blocking
    from packages.db.models.failure_family import SuppressionRule
    ff_rules = list((await db.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand_id, SuppressionRule.is_active.is_(True), SuppressionRule.family_type == "content_form")
    )).scalars().all())
    suppressed_forms = {r.family_key for r in ff_rules}
    for rec in rec_rows:
        if rec.recommended_content_form in suppressed_forms:
            rec.confidence = max(0.0, float(rec.confidence or 0) - 0.5)

    await db.flush()
    await recompute_blockers(db, brand_id)
    return {"rows_processed": len(all_recs), "status": "completed"}


async def recompute_mix(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    rows = list((await db.execute(
        select(ContentFormRecommendation).where(
            ContentFormRecommendation.brand_id == brand_id,
            ContentFormRecommendation.is_active.is_(True),
        )
    )).scalars().all())

    rec_dicts = [
        {
            "platform": r.platform,
            "recommended_content_form": r.recommended_content_form,
            "expected_upside": r.expected_upside,
            "confidence": r.confidence,
        }
        for r in rows
    ]

    reports = compute_mix_reports(rec_dicts)

    await db.execute(delete(ContentFormMixReport).where(ContentFormMixReport.brand_id == brand_id))

    for rpt in reports:
        db.add(ContentFormMixReport(brand_id=brand_id, **rpt))

    await db.flush()
    return {"rows_processed": len(reports), "status": "completed"}


async def recompute_blockers(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    has_avatar = bool(os.getenv("TAVUS_API_KEY") or os.getenv("HEYGEN_API_KEY"))
    has_voice = bool(os.getenv("ELEVENLABS_API_KEY"))

    content_count = (await db.execute(
        select(func.count(ContentItem.id)).where(ContentItem.brand_id == brand_id)
    )).scalar() or 0

    offer_count = (await db.execute(
        select(func.count(Offer.id)).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalar() or 0

    blockers = detect_content_form_blockers(
        has_avatar=has_avatar,
        has_voice=has_voice,
        content_count=int(content_count),
        offer_count=int(offer_count),
    )

    await db.execute(delete(ContentFormBlocker).where(ContentFormBlocker.brand_id == brand_id))

    for b in blockers:
        db.add(ContentFormBlocker(brand_id=brand_id, **b))

    await db.flush()
    return {"rows_processed": len(blockers), "status": "completed"}


async def list_recommendations(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ContentFormRecommendation)
        .where(ContentFormRecommendation.brand_id == brand_id, ContentFormRecommendation.is_active.is_(True))
        .order_by(ContentFormRecommendation.confidence.desc())
    )).scalars().all())


async def list_mix_reports(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ContentFormMixReport)
        .where(ContentFormMixReport.brand_id == brand_id, ContentFormMixReport.is_active.is_(True))
        .order_by(ContentFormMixReport.total_expected_upside.desc())
    )).scalars().all())


async def list_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(ContentFormBlocker)
        .where(ContentFormBlocker.brand_id == brand_id, ContentFormBlocker.is_active.is_(True))
        .order_by(ContentFormBlocker.severity.asc())
    )).scalars().all())
