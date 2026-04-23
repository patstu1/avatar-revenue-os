"""Service layer for Creator Revenue Avenues Phase A."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.creator_revenue import (
    AvenueExecutionTruth,
    CreatorRevenueBlocker,
    CreatorRevenueEvent,
    CreatorRevenueOpportunity,
    DataProductAction,
    LicensingAction,
    LiveEventAction,
    MerchAction,
    OwnedAffiliateProgramAction,
    PremiumAccessAction,
    ServiceConsultingAction,
    SyndicationAction,
    UgcServiceAction,
)
from packages.scoring.creator_revenue_engine import (
    AVENUE_DISPLAY_NAMES,
    AVENUE_MISSING_INTEGRATIONS,
    AVENUE_TYPES,
    build_event_rollup,
    build_revenue_opportunities,
    classify_avenue_truth_state,
    detect_creator_revenue_blockers,
    detect_phase_b_blockers,
    detect_phase_c_blockers,
    determine_operator_next_action,
    rank_hub_entries,
    score_consulting_opportunities,
    score_data_product_opportunities,
    score_licensing_opportunities,
    score_live_event_opportunities,
    score_merch_opportunities,
    score_owned_affiliate_opportunities,
    score_premium_access_opportunities,
    score_syndication_opportunities,
    score_ugc_opportunity,
)


async def _brand_context(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    from packages.db.models.content import ContentItem
    from packages.db.models.core import Avatar, Brand
    from packages.db.models.offers import Offer
    from packages.db.models.accounts import CreatorAccount

    brand_q = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_q.scalar_one_or_none()
    niche = brand.niche if brand and brand.niche else "general"

    content_count = (await db.execute(
        select(func.count()).select_from(ContentItem).where(ContentItem.brand_id == brand_id)
    )).scalar() or 0

    offer_count = (await db.execute(
        select(func.count()).select_from(Offer).where(Offer.brand_id == brand_id)
    )).scalar() or 0

    avatar_count = (await db.execute(
        select(func.count()).select_from(Avatar).where(Avatar.brand_id == brand_id)
    )).scalar() or 0

    account_count = (await db.execute(
        select(func.count()).select_from(CreatorAccount).where(CreatorAccount.brand_id == brand_id)
    )).scalar() or 0

    return {
        "niche": niche,
        "content_count": content_count,
        "offer_count": offer_count,
        "has_avatar": avatar_count > 0,
        "account_count": account_count,
        "audience_size": account_count * 2500,
        "has_community": False,
        "has_payment_processor": False,
        "has_landing_page": offer_count > 0,
    }


# ── Opportunities ──────────────────────────────────────────────────────

async def list_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> list[CreatorRevenueOpportunity]:
    q = select(CreatorRevenueOpportunity).where(
        CreatorRevenueOpportunity.brand_id == brand_id,
        CreatorRevenueOpportunity.is_active.is_(True),
    ).order_by(CreatorRevenueOpportunity.priority_score.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(CreatorRevenueOpportunity)
        .where(CreatorRevenueOpportunity.brand_id == brand_id, CreatorRevenueOpportunity.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    opps = build_revenue_opportunities(
        ugc_plans=score_ugc_opportunity(ctx),
        consulting_plans=score_consulting_opportunities(ctx),
        premium_plans=score_premium_access_opportunities(ctx),
        licensing_plans=score_licensing_opportunities(ctx),
        syndication_plans=score_syndication_opportunities(ctx),
        data_product_plans=score_data_product_opportunities(ctx),
        merch_plans=score_merch_opportunities(ctx),
        live_event_plans=score_live_event_opportunities(ctx),
        affiliate_plans=score_owned_affiliate_opportunities(ctx),
    )

    for o in opps:
        db.add(CreatorRevenueOpportunity(brand_id=brand_id, **o))

    await db.commit()
    return {"created": len(opps), "updated": 0}


# ── UGC Services ───────────────────────────────────────────────────────

async def list_ugc_services(db: AsyncSession, brand_id: uuid.UUID) -> list[UgcServiceAction]:
    q = select(UgcServiceAction).where(
        UgcServiceAction.brand_id == brand_id,
        UgcServiceAction.is_active.is_(True),
    ).order_by(UgcServiceAction.expected_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_ugc_services(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(UgcServiceAction)
        .where(UgcServiceAction.brand_id == brand_id, UgcServiceAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_ugc_opportunity(ctx)

    for p in plans:
        db.add(UgcServiceAction(
            brand_id=brand_id,
            service_type=p["service_type"],
            target_segment=p["target_segment"],
            recommended_package=p["recommended_package"],
            price_band=p["price_band"],
            expected_value=p["expected_value"],
            expected_margin=p["expected_margin"],
            execution_steps_json=p["execution_steps"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Service / Consulting ───────────────────────────────────────────────

async def list_service_consulting(db: AsyncSession, brand_id: uuid.UUID) -> list[ServiceConsultingAction]:
    q = select(ServiceConsultingAction).where(
        ServiceConsultingAction.brand_id == brand_id,
        ServiceConsultingAction.is_active.is_(True),
    ).order_by(ServiceConsultingAction.expected_deal_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_service_consulting(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(ServiceConsultingAction)
        .where(ServiceConsultingAction.brand_id == brand_id, ServiceConsultingAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_consulting_opportunities(ctx)

    for p in plans:
        db.add(ServiceConsultingAction(
            brand_id=brand_id,
            service_type=p["service_type"],
            service_tier=p["service_tier"],
            target_buyer=p["target_buyer"],
            price_band=p["price_band"],
            expected_deal_value=p["expected_deal_value"],
            execution_plan_json=p["execution_plan"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Premium Access ─────────────────────────────────────────────────────

async def list_premium_access(db: AsyncSession, brand_id: uuid.UUID) -> list[PremiumAccessAction]:
    q = select(PremiumAccessAction).where(
        PremiumAccessAction.brand_id == brand_id,
        PremiumAccessAction.is_active.is_(True),
    ).order_by(PremiumAccessAction.expected_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_premium_access(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(PremiumAccessAction)
        .where(PremiumAccessAction.brand_id == brand_id, PremiumAccessAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_premium_access_opportunities(ctx)

    for p in plans:
        db.add(PremiumAccessAction(
            brand_id=brand_id,
            offer_type=p["offer_type"],
            target_segment=p["target_segment"],
            entry_criteria=p["entry_criteria"],
            revenue_model=p["revenue_model"],
            expected_value=p["expected_value"],
            execution_plan_json=p["execution_plan"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Blockers ───────────────────────────────────────────────────────────

async def list_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list[CreatorRevenueBlocker]:
    q = select(CreatorRevenueBlocker).where(
        CreatorRevenueBlocker.brand_id == brand_id,
        CreatorRevenueBlocker.is_active.is_(True),
    ).order_by(CreatorRevenueBlocker.created_at.desc()).limit(50)
    return list((await db.execute(q)).scalars().all())


async def recompute_blockers(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(CreatorRevenueBlocker)
        .where(CreatorRevenueBlocker.brand_id == brand_id, CreatorRevenueBlocker.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    blockers = (
        detect_creator_revenue_blockers(ctx)
        + detect_phase_b_blockers(ctx)
        + detect_phase_c_blockers(ctx)
    )

    for b in blockers:
        db.add(CreatorRevenueBlocker(brand_id=brand_id, **b))

    await db.commit()
    return {"created": len(blockers), "updated": 0}


# ── Licensing (Phase B) ───────────────────────────────────────────────

async def list_licensing(db: AsyncSession, brand_id: uuid.UUID) -> list[LicensingAction]:
    q = select(LicensingAction).where(
        LicensingAction.brand_id == brand_id,
        LicensingAction.is_active.is_(True),
    ).order_by(LicensingAction.expected_deal_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_licensing(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(LicensingAction)
        .where(LicensingAction.brand_id == brand_id, LicensingAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_licensing_opportunities(ctx)

    for p in plans:
        db.add(LicensingAction(
            brand_id=brand_id,
            asset_type=p["asset_type"],
            licensing_tier=p["licensing_tier"],
            target_buyer_type=p["target_buyer_type"],
            usage_scope=p["usage_scope"],
            price_band=p["price_band"],
            expected_deal_value=p["expected_deal_value"],
            execution_plan_json=p["execution_plan"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Syndication (Phase B) ─────────────────────────────────────────────

async def list_syndication(db: AsyncSession, brand_id: uuid.UUID) -> list[SyndicationAction]:
    q = select(SyndicationAction).where(
        SyndicationAction.brand_id == brand_id,
        SyndicationAction.is_active.is_(True),
    ).order_by(SyndicationAction.expected_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_syndication(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(SyndicationAction)
        .where(SyndicationAction.brand_id == brand_id, SyndicationAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_syndication_opportunities(ctx)

    for p in plans:
        db.add(SyndicationAction(
            brand_id=brand_id,
            syndication_format=p["syndication_format"],
            target_partner=p["target_partner"],
            revenue_model=p["revenue_model"],
            price_band=p["price_band"],
            expected_value=p["expected_value"],
            execution_plan_json=p["execution_plan"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Data Products (Phase B) ───────────────────────────────────────────

async def list_data_products(db: AsyncSession, brand_id: uuid.UUID) -> list[DataProductAction]:
    q = select(DataProductAction).where(
        DataProductAction.brand_id == brand_id,
        DataProductAction.is_active.is_(True),
    ).order_by(DataProductAction.expected_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_data_products(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(DataProductAction)
        .where(DataProductAction.brand_id == brand_id, DataProductAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_data_product_opportunities(ctx)

    for p in plans:
        db.add(DataProductAction(
            brand_id=brand_id,
            product_type=p["product_type"],
            target_segment=p["target_segment"],
            revenue_model=p["revenue_model"],
            price_band=p["price_band"],
            expected_value=p["expected_value"],
            execution_plan_json=p["execution_plan"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Merch (Phase C) ────────────────────────────────────────────────────

async def list_merch(db: AsyncSession, brand_id: uuid.UUID) -> list[MerchAction]:
    q = select(MerchAction).where(
        MerchAction.brand_id == brand_id,
        MerchAction.is_active.is_(True),
    ).order_by(MerchAction.expected_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_merch(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(MerchAction)
        .where(MerchAction.brand_id == brand_id, MerchAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_merch_opportunities(ctx)

    for p in plans:
        db.add(MerchAction(
            brand_id=brand_id,
            product_class=p["product_class"],
            target_segment=p["target_segment"],
            price_band=p["price_band"],
            expected_value=p["expected_value"],
            execution_plan_json=p["execution_plan"],
            truth_label=p["truth_label"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Live Events (Phase C) ─────────────────────────────────────────────

async def list_live_events(db: AsyncSession, brand_id: uuid.UUID) -> list[LiveEventAction]:
    q = select(LiveEventAction).where(
        LiveEventAction.brand_id == brand_id,
        LiveEventAction.is_active.is_(True),
    ).order_by(LiveEventAction.expected_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_live_events(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(LiveEventAction)
        .where(LiveEventAction.brand_id == brand_id, LiveEventAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_live_event_opportunities(ctx)

    for p in plans:
        db.add(LiveEventAction(
            brand_id=brand_id,
            event_type=p["event_type"],
            audience_segment=p["audience_segment"],
            ticket_model=p["ticket_model"],
            price_band=p["price_band"],
            expected_value=p["expected_value"],
            execution_plan_json=p["execution_plan"],
            truth_label=p["truth_label"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Owned Affiliate Program (Phase C) ─────────────────────────────────

async def list_owned_affiliate_program(db: AsyncSession, brand_id: uuid.UUID) -> list[OwnedAffiliateProgramAction]:
    q = select(OwnedAffiliateProgramAction).where(
        OwnedAffiliateProgramAction.brand_id == brand_id,
        OwnedAffiliateProgramAction.is_active.is_(True),
    ).order_by(OwnedAffiliateProgramAction.expected_value.desc()).limit(100)
    return list((await db.execute(q)).scalars().all())


async def recompute_owned_affiliate_program(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(OwnedAffiliateProgramAction)
        .where(OwnedAffiliateProgramAction.brand_id == brand_id, OwnedAffiliateProgramAction.is_active.is_(True))
        .values(is_active=False)
    )

    ctx = await _brand_context(db, brand_id)
    plans = score_owned_affiliate_opportunities(ctx)

    for p in plans:
        db.add(OwnedAffiliateProgramAction(
            brand_id=brand_id,
            program_type=p["program_type"],
            target_partner_type=p["target_partner_type"],
            incentive_model=p["incentive_model"],
            partner_tier=p["partner_tier"],
            expected_value=p["expected_value"],
            execution_plan_json=p["execution_plan"],
            truth_label=p["truth_label"],
            confidence=p["confidence"],
            explanation=p["explanation"],
        ))

    await db.commit()
    return {"created": len(plans), "updated": 0}


# ── Phase D: Unified Hub ───────────────────────────────────────────────

_AVENUE_ACTION_MODELS = {
    "ugc_services": (UgcServiceAction, "expected_value", "status", None),
    "consulting": (ServiceConsultingAction, "expected_deal_value", "status", None),
    "premium_access": (PremiumAccessAction, "expected_value", "status", None),
    "licensing": (LicensingAction, "expected_deal_value", "status", None),
    "syndication": (SyndicationAction, "expected_value", "status", None),
    "data_products": (DataProductAction, "expected_value", "status", None),
    "merch": (MerchAction, "expected_value", "truth_label", "truth_label"),
    "live_events": (LiveEventAction, "expected_value", "truth_label", "truth_label"),
    "owned_affiliate_program": (OwnedAffiliateProgramAction, "expected_value", "truth_label", "truth_label"),
}


async def _gather_avenue_stats(db: AsyncSession, brand_id: uuid.UUID, avenue_type: str) -> dict:
    model, value_col, status_col, truth_col = _AVENUE_ACTION_MODELS[avenue_type]

    total_q = select(func.count()).select_from(model).where(model.brand_id == brand_id, model.is_active.is_(True))
    total = (await db.execute(total_q)).scalar() or 0

    value_q = select(
        func.coalesce(func.sum(getattr(model, value_col)), 0),
        func.coalesce(func.avg(model.confidence), 0),
    ).where(model.brand_id == brand_id, model.is_active.is_(True))
    row = (await db.execute(value_q)).one()
    total_value = float(row[0])
    avg_conf = float(row[1])

    blocked = 0
    if truth_col:
        blocked_q = select(func.count()).select_from(model).where(
            model.brand_id == brand_id, model.is_active.is_(True),
            getattr(model, truth_col) == "blocked",
        )
        blocked = (await db.execute(blocked_q)).scalar() or 0

    blocker_q = select(func.count()).select_from(CreatorRevenueBlocker).where(
        CreatorRevenueBlocker.brand_id == brand_id,
        CreatorRevenueBlocker.is_active.is_(True),
        CreatorRevenueBlocker.avenue_type.in_([avenue_type, "all"]),
    )
    blocker_count = (await db.execute(blocker_q)).scalar() or 0

    blocker_types_q = select(CreatorRevenueBlocker.blocker_type).where(
        CreatorRevenueBlocker.brand_id == brand_id,
        CreatorRevenueBlocker.is_active.is_(True),
        CreatorRevenueBlocker.avenue_type.in_([avenue_type, "all"]),
    )
    blocker_types = list((await db.execute(blocker_types_q)).scalars().all())

    rev_q = select(func.coalesce(func.sum(CreatorRevenueEvent.revenue), 0)).where(
        CreatorRevenueEvent.brand_id == brand_id,
        CreatorRevenueEvent.is_active.is_(True),
        CreatorRevenueEvent.avenue_type == avenue_type,
    )
    revenue_to_date = float((await db.execute(rev_q)).scalar() or 0)

    has_revenue = revenue_to_date > 0
    truth_state = classify_avenue_truth_state(total, blocked, blocker_count, has_revenue)
    next_action = determine_operator_next_action(avenue_type, truth_state, blocker_types)

    return {
        "avenue_type": avenue_type,
        "avenue_display_name": AVENUE_DISPLAY_NAMES.get(avenue_type, avenue_type),
        "truth_state": truth_state,
        "total_actions": total,
        "active_actions": total - blocked,
        "blocked_actions": blocked,
        "total_expected_value": round(total_value, 2),
        "avg_confidence": round(avg_conf, 3),
        "blocker_count": blocker_count,
        "revenue_to_date": round(revenue_to_date, 2),
        "operator_next_action": next_action,
        "missing_integrations": AVENUE_MISSING_INTEGRATIONS.get(avenue_type, []),
        "top_blockers": blocker_types[:5],
    }


async def get_hub(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    entries = []
    for avenue_type in AVENUE_TYPES:
        stats = await _gather_avenue_stats(db, brand_id, avenue_type)
        entries.append(stats)

    ranked = rank_hub_entries(entries)

    event_q = select(CreatorRevenueEvent).where(
        CreatorRevenueEvent.brand_id == brand_id,
        CreatorRevenueEvent.is_active.is_(True),
    )
    events_raw = list((await db.execute(event_q)).scalars().all())
    events_dicts = [{"avenue_type": e.avenue_type, "revenue": e.revenue, "cost": e.cost, "profit": e.profit} for e in events_raw]
    rollup = build_event_rollup(events_dicts)

    total_ev = sum(e["total_expected_value"] for e in ranked)
    total_rev = sum(e["revenue_to_date"] for e in ranked)
    total_bl = sum(e["blocker_count"] for e in ranked)

    return {
        "entries": ranked,
        "total_expected_value": round(total_ev, 2),
        "total_revenue_to_date": round(total_rev, 2),
        "total_blockers": total_bl,
        "avenues_live": sum(1 for e in ranked if e["truth_state"] == "live"),
        "avenues_blocked": sum(1 for e in ranked if e["truth_state"] == "blocked"),
        "avenues_executing": sum(1 for e in ranked if e["truth_state"] == "executing"),
        "avenues_queued": sum(1 for e in ranked if e["truth_state"] == "queued"),
        "avenues_recommended": sum(1 for e in ranked if e["truth_state"] == "recommended"),
        "event_rollup": rollup,
    }


async def recompute_hub(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    await db.execute(
        update(AvenueExecutionTruth)
        .where(AvenueExecutionTruth.brand_id == brand_id, AvenueExecutionTruth.is_active.is_(True))
        .values(is_active=False)
    )

    created = 0
    for avenue_type in AVENUE_TYPES:
        stats = await _gather_avenue_stats(db, brand_id, avenue_type)
        db.add(AvenueExecutionTruth(
            brand_id=brand_id,
            avenue_type=stats["avenue_type"],
            truth_state=stats["truth_state"],
            total_actions=stats["total_actions"],
            active_actions=stats["active_actions"],
            blocked_actions=stats["blocked_actions"],
            total_expected_value=stats["total_expected_value"],
            avg_confidence=stats["avg_confidence"],
            blocker_count=stats["blocker_count"],
            revenue_to_date=stats["revenue_to_date"],
            operator_next_action=stats["operator_next_action"],
            missing_integrations=stats["missing_integrations"],
            details_json={"top_blockers": stats["top_blockers"]},
        ))
        created += 1

    await db.commit()
    return {"created": created, "updated": 0}


async def list_truth(db: AsyncSession, brand_id: uuid.UUID) -> list[AvenueExecutionTruth]:
    q = select(AvenueExecutionTruth).where(
        AvenueExecutionTruth.brand_id == brand_id,
        AvenueExecutionTruth.is_active.is_(True),
    ).order_by(AvenueExecutionTruth.total_expected_value.desc()).limit(20)
    return list((await db.execute(q)).scalars().all())


# ── Events ─────────────────────────────────────────────────────────────

async def list_events(db: AsyncSession, brand_id: uuid.UUID) -> list[CreatorRevenueEvent]:
    q = select(CreatorRevenueEvent).where(
        CreatorRevenueEvent.brand_id == brand_id,
        CreatorRevenueEvent.is_active.is_(True),
    ).order_by(CreatorRevenueEvent.created_at.desc()).limit(200)
    return list((await db.execute(q)).scalars().all())
