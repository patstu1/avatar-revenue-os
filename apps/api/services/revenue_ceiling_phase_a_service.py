"""Revenue Ceiling Phase A — offer ladders, owned audience, sequences, funnel metrics/leaks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.revenue_ceiling_phase_a import (
    FunnelLeakFix,
    FunnelStageMetric,
    MessageSequence,
    MessageSequenceStep,
    OfferLadder,
    OwnedAudienceAsset,
    OwnedAudienceEvent,
)
from packages.scoring.revenue_ceiling_phase_a_engines import (
    RC_PHASE_A,
    compute_funnel_stage_metrics,
    detect_funnel_leaks,
    generate_all_message_sequences,
    generate_offer_ladders,
    generate_owned_audience_assets,
    synthesize_owned_audience_events,
)


def _strip_meta(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != RC_PHASE_A}


def _content_families_from_items(items: list[ContentItem]) -> list[str]:
    """Distinct content family labels from tags (aligned with owned-audience logic)."""
    families: list[str] = []
    for ci in items:
        fam = "general"
        if ci.tags:
            if isinstance(ci.tags, dict):
                fam = str(ci.tags.get("family", "general"))
            elif isinstance(ci.tags, list) and ci.tags:
                fam = str(ci.tags[0])[:120]
        families.append(fam)
    out = list(dict.fromkeys(families)) or ["general"]
    return out[:12]


async def recompute_offer_ladders(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(50))).scalars().all()
    )
    offer_dicts = [
        {
            "id": str(o.id),
            "name": o.name,
            "epc": float(o.epc or 0),
            "conversion_rate": float(o.conversion_rate or 0),
            "average_order_value": float(o.average_order_value or 0),
        }
        for o in offers
    ]
    content_dicts = [{"id": str(ci.id), "title": ci.title} for ci in items]
    rows = generate_offer_ladders(brand.niche or "general", offer_dicts, content_dicts)
    await db.execute(delete(OfferLadder).where(OfferLadder.brand_id == brand_id))
    for r in rows:
        r = _strip_meta(r)
        ol = OfferLadder(
            brand_id=brand_id,
            opportunity_key=r["opportunity_key"],
            content_item_id=uuid.UUID(r["content_item_id"]) if r.get("content_item_id") else None,
            offer_id=uuid.UUID(r["offer_id"]) if r.get("offer_id") else None,
            top_of_funnel_asset=r.get("top_of_funnel_asset", ""),
            first_monetization_step=r.get("first_monetization_step", ""),
            second_monetization_step=r.get("second_monetization_step", ""),
            upsell_path=r.get("upsell_path"),
            retention_path=r.get("retention_path"),
            fallback_path=r.get("fallback_path"),
            ladder_recommendation=r.get("ladder_recommendation"),
            expected_first_conversion_value=float(r.get("expected_first_conversion_value", 0)),
            expected_downstream_value=float(r.get("expected_downstream_value", 0)),
            expected_ltv_contribution=float(r.get("expected_ltv_contribution", 0)),
            friction_level=r.get("friction_level", "medium"),
            confidence=float(r.get("confidence", 0)),
            explanation=r.get("explanation"),
        )
        db.add(ol)
    await db.flush()
    return {"offer_ladders_created": len(rows)}


async def recompute_owned_audience(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")
    items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(100))).scalars().all()
    )
    families = _content_families_from_items(items)
    assets_raw = generate_owned_audience_assets(brand.niche or "general", families)
    await db.execute(delete(OwnedAudienceEvent).where(OwnedAudienceEvent.brand_id == brand_id))
    await db.execute(delete(OwnedAudienceAsset).where(OwnedAudienceAsset.brand_id == brand_id))
    asset_ids: list[uuid.UUID] = []
    for a in assets_raw:
        a = _strip_meta(a)
        oa = OwnedAudienceAsset(
            brand_id=brand_id,
            asset_type=a["asset_type"],
            channel_name=a.get("channel_name", ""),
            content_family=a.get("content_family"),
            objective_per_family=a.get("objective_per_family"),
            cta_variants=a.get("cta_variants"),
            estimated_channel_value=float(a.get("estimated_channel_value", 0)),
            direct_vs_capture_score=float(a.get("direct_vs_capture_score", 0.5)),
        )
        db.add(oa)
        await db.flush()
        asset_ids.append(oa.id)
    content_dicts = [{"id": str(ci.id), "title": ci.title} for ci in items]
    ev_raw = synthesize_owned_audience_events(content_dicts, [str(x) for x in asset_ids])
    for e in ev_raw:
        oe = OwnedAudienceEvent(
            brand_id=brand_id,
            content_item_id=uuid.UUID(e["content_item_id"]) if e.get("content_item_id") else None,
            asset_id=uuid.UUID(e["asset_id"]) if e.get("asset_id") else None,
            event_type=e["event_type"],
            value_contribution=float(e.get("value_contribution", 0)),
            source_metadata=e.get("source_metadata"),
        )
        db.add(oe)
    await db.flush()
    return {"owned_audience_assets": len(assets_raw), "owned_audience_events": len(ev_raw)}


async def generate_message_sequences(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")
    await db.execute(
        delete(MessageSequenceStep).where(
            MessageSequenceStep.sequence_id.in_(select(MessageSequence.id).where(MessageSequence.brand_id == brand_id))
        )
    )
    await db.execute(delete(MessageSequence).where(MessageSequence.brand_id == brand_id))
    seqs = generate_all_message_sequences(brand_voice=brand.niche or "expert")
    total_steps = 0
    for meta, steps in seqs:
        ch = meta["channel"]
        if ch == "hybrid":
            ch_store = "hybrid"
        elif ch == "sms":
            ch_store = "sms"
        else:
            ch_store = "email"
        ms = MessageSequence(
            brand_id=brand_id,
            sequence_type=meta["sequence_type"],
            channel=ch_store,
            title=meta["title"],
            sponsor_safe=meta.get("sponsor_safe", False),
        )
        db.add(ms)
        await db.flush()
        for s in steps:
            db.add(
                MessageSequenceStep(
                    sequence_id=ms.id,
                    step_order=s["step_order"],
                    channel=s.get("channel", "email"),
                    subject_or_title=s.get("subject_or_title"),
                    body_template=s.get("body_template"),
                    delay_hours_after_previous=int(s.get("delay_hours_after_previous", 0)),
                )
            )
            total_steps += 1
    await db.flush()
    return {"sequences_created": len(seqs), "steps_created": total_steps}


async def recompute_funnel_leaks(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")
    items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(100))).scalars().all()
    )
    families = _content_families_from_items(items)
    metrics: list[dict[str, Any]] = []
    leaks: list[dict[str, Any]] = []
    for fam in families:
        mets = compute_funnel_stage_metrics(fam)
        metrics.extend(mets)
        leaks.extend(detect_funnel_leaks(mets, fam))
    await db.execute(delete(FunnelLeakFix).where(FunnelLeakFix.brand_id == brand_id))
    await db.execute(delete(FunnelStageMetric).where(FunnelStageMetric.brand_id == brand_id))
    now = datetime.now(timezone.utc).date().isoformat()
    for m in metrics:
        db.add(
            FunnelStageMetric(
                brand_id=brand_id,
                content_family=m["content_family"],
                stage=m["stage"],
                metric_value=float(m["metric_value"]),
                sample_size=int(m["sample_size"]),
                period_start=now,
                period_end=now,
            )
        )
    for L in leaks:
        db.add(
            FunnelLeakFix(
                brand_id=brand_id,
                leak_type=L["leak_type"],
                severity=L["severity"],
                affected_funnel_stage=L["affected_funnel_stage"],
                affected_content_family=L.get("affected_content_family"),
                suspected_cause=L.get("suspected_cause"),
                recommended_fix=L.get("recommended_fix"),
                expected_upside=float(L.get("expected_upside", 0)),
                confidence=float(L.get("confidence", 0)),
                urgency=float(L.get("urgency", 0)),
            )
        )
    await db.flush()
    return {"funnel_metrics": len(metrics), "funnel_leaks": len(leaks)}


def _ladder_dict(x: OfferLadder) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "opportunity_key": x.opportunity_key,
        "content_item_id": str(x.content_item_id) if x.content_item_id else None,
        "offer_id": str(x.offer_id) if x.offer_id else None,
        "top_of_funnel_asset": x.top_of_funnel_asset,
        "first_monetization_step": x.first_monetization_step,
        "second_monetization_step": x.second_monetization_step,
        "upsell_path": x.upsell_path,
        "retention_path": x.retention_path,
        "fallback_path": x.fallback_path,
        "ladder_recommendation": x.ladder_recommendation,
        "expected_first_conversion_value": x.expected_first_conversion_value,
        "expected_downstream_value": x.expected_downstream_value,
        "expected_ltv_contribution": x.expected_ltv_contribution,
        "friction_level": x.friction_level,
        "confidence": x.confidence,
        "explanation": x.explanation,
    }


async def get_offer_ladders(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list(
        (await db.execute(select(OfferLadder).where(OfferLadder.brand_id == brand_id, OfferLadder.is_active.is_(True))))
        .scalars()
        .all()
    )
    return [_ladder_dict(r) for r in rows]


async def get_owned_audience_bundle(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    assets = list(
        (
            await db.execute(
                select(OwnedAudienceAsset).where(
                    OwnedAudienceAsset.brand_id == brand_id, OwnedAudienceAsset.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    events = list(
        (
            await db.execute(
                select(OwnedAudienceEvent)
                .where(OwnedAudienceEvent.brand_id == brand_id)
                .order_by(OwnedAudienceEvent.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return {
        "assets": [
            {
                "id": str(a.id),
                "asset_type": a.asset_type,
                "channel_name": a.channel_name,
                "content_family": a.content_family,
                "objective_per_family": a.objective_per_family,
                "cta_variants": a.cta_variants,
                "estimated_channel_value": a.estimated_channel_value,
                "direct_vs_capture_score": a.direct_vs_capture_score,
            }
            for a in assets
        ],
        "events": [
            {
                "id": str(e.id),
                "content_item_id": str(e.content_item_id) if e.content_item_id else None,
                "asset_id": str(e.asset_id) if e.asset_id else None,
                "event_type": e.event_type,
                "value_contribution": e.value_contribution,
                "source_metadata": e.source_metadata,
                "created_at": str(e.created_at),
            }
            for e in events
        ],
    }


async def get_message_sequences(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    seqs = list(
        (
            await db.execute(
                select(MessageSequence).where(MessageSequence.brand_id == brand_id, MessageSequence.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    out: list[dict] = []
    for s in seqs:
        steps = list(
            (
                await db.execute(
                    select(MessageSequenceStep)
                    .where(MessageSequenceStep.sequence_id == s.id)
                    .order_by(MessageSequenceStep.step_order)
                )
            )
            .scalars()
            .all()
        )
        out.append(
            {
                "id": str(s.id),
                "sequence_type": s.sequence_type,
                "channel": s.channel,
                "title": s.title,
                "sponsor_safe": s.sponsor_safe,
                "steps": [
                    {
                        "id": str(st.id),
                        "step_order": st.step_order,
                        "channel": st.channel,
                        "subject_or_title": st.subject_or_title,
                        "body_template": st.body_template,
                        "delay_hours_after_previous": st.delay_hours_after_previous,
                    }
                    for st in steps
                ],
            }
        )
    return out


async def get_funnel_stage_metrics(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list(
        (await db.execute(select(FunnelStageMetric).where(FunnelStageMetric.brand_id == brand_id))).scalars().all()
    )
    return [
        {
            "id": str(r.id),
            "content_family": r.content_family,
            "stage": r.stage,
            "metric_value": r.metric_value,
            "sample_size": r.sample_size,
            "period_start": r.period_start,
            "period_end": r.period_end,
        }
        for r in rows
    ]


async def get_funnel_leaks(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list(
        (
            await db.execute(
                select(FunnelLeakFix).where(FunnelLeakFix.brand_id == brand_id, FunnelLeakFix.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "leak_type": r.leak_type,
            "severity": r.severity,
            "affected_funnel_stage": r.affected_funnel_stage,
            "affected_content_family": r.affected_content_family,
            "suspected_cause": r.suspected_cause,
            "recommended_fix": r.recommended_fix,
            "expected_upside": r.expected_upside,
            "confidence": r.confidence,
            "urgency": r.urgency,
        }
        for r in rows
    ]
