"""Creative memory service — index reusable content atoms, persist and retrieve."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.creative_memory import CreativeMemoryAtom, CreativeMemoryLink
from packages.db.models.experiment_decisions import ExperimentOutcome
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.creative_memory_engine import CREATIVE_MEMORY, index_creative_atoms


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != CREATIVE_MEMORY}


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


async def recompute_creative_memory(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    content_items = list(
        (
            await db.execute(
                select(ContentItem)
                .where(ContentItem.brand_id == brand_id)
                .order_by(ContentItem.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )

    perf_rows = list(
        (await db.execute(select(PerformanceMetric).where(PerformanceMetric.brand_id == brand_id).limit(500)))
        .scalars()
        .all()
    )
    performance_data: list[dict[str, Any]] = [
        {
            "content_item_id": str(pm.content_item_id),
            "engagement_rate": float(pm.engagement_rate or 0),
            "conversion_rate": 0.0,
        }
        for pm in perf_rows
    ]

    ci_dicts: list[dict[str, Any]] = []
    for ci in content_items:
        platform_val = getattr(ci, "platform", None)
        if platform_val is not None and hasattr(platform_val, "value"):
            platform_str = platform_val.value
        else:
            platform_str = str(platform_val) if platform_val else None

        ci_dicts.append(
            {
                "id": str(ci.id),
                "title": ci.title or "",
                "body": getattr(ci, "body", None) or getattr(ci, "text", None) or "",
                "platform": platform_str,
                "niche": brand.niche,
                "monetization_type": None,
                "funnel_stage": None,
                "reuse_count": 0,
            }
        )

    outcome_types = list(
        (await db.execute(select(ExperimentOutcome.outcome_type).where(ExperimentOutcome.brand_id == brand_id)))
        .scalars()
        .all()
    )
    oc_counts = Counter(outcome_types)
    promote_boost = min(0.08, 0.02 * int(oc_counts.get("promote", 0))) if oc_counts else 0.0

    brand_context = {
        "niche": brand.niche or "general",
        "default_platform": "youtube",
        "default_monetization_type": "affiliate",
        "experiment_outcome_confidence_boost": promote_boost,
    }

    atoms = index_creative_atoms(ci_dicts, performance_data, brand_context)

    if oc_counts:
        atoms.append(
            {
                "content_item_id": None,
                "atom_type": "experiment_learned_signal",
                "content_json": {
                    "source": "experiment_outcomes",
                    "counts": dict(oc_counts),
                    "note": "Signals from persisted experiment outcomes influence atom confidence boost.",
                },
                "niche": brand.niche or "general",
                "platform": brand_context.get("default_platform", "youtube"),
                "monetization_type": brand_context.get("default_monetization_type", "affiliate"),
                "funnel_stage": "experimentation",
                "performance_summary": {
                    "avg_engagement": 0.0,
                    "avg_conversion": 0.0,
                    "sample_size": sum(oc_counts.values()),
                },
                "reuse_recommendations": [
                    "Reuse winning angles from promoted variants.",
                    "Deprioritize hooks tied to suppressed experiments.",
                ],
                "originality_caution_score": 0.15,
                "confidence": min(0.92, 0.45 + promote_boost * 3),
                "explanation": f"Experiment outcome memory: {dict(oc_counts)}",
                CREATIVE_MEMORY: True,
            }
        )

    await db.execute(delete(CreativeMemoryLink).where(CreativeMemoryLink.brand_id == brand_id))
    await db.execute(
        delete(CreativeMemoryAtom).where(
            CreativeMemoryAtom.brand_id == brand_id,
            CreativeMemoryAtom.is_active.is_(True),
        )
    )

    atom_count = 0
    for item in atoms:
        r = _strip_meta(item)

        atom = CreativeMemoryAtom(
            brand_id=brand_id,
            atom_type=r.get("atom_type", "opening"),
            content_json=r.get("content_json", {}),
            niche=r.get("niche"),
            audience_segment_id=None,
            platform=r.get("platform"),
            monetization_type=r.get("monetization_type"),
            account_type=None,
            funnel_stage=r.get("funnel_stage"),
            performance_summary_json=r.get("performance_summary", {}),
            reuse_recommendations_json=r.get("reuse_recommendations", []),
            originality_caution_score=float(r.get("originality_caution_score", 0)),
            confidence_score=float(r.get("confidence", 0.5)),
            is_active=True,
        )
        db.add(atom)

        content_item_id = r.get("content_item_id")
        if content_item_id:
            try:
                ci_uuid = uuid.UUID(content_item_id)
                db.add(
                    CreativeMemoryLink(
                        brand_id=brand_id,
                        atom_id=atom.id,
                        linked_scope_type="content_item",
                        linked_scope_id=ci_uuid,
                        relationship_type="extracted_from",
                    )
                )
            except (ValueError, AttributeError):
                logger.debug("creative_memory_link_content_id_parse_failed", exc_info=True)

        atom_count += 1

    await db.flush()
    return {"creative_atoms": atom_count}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _atom_dict(x: CreativeMemoryAtom) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "atom_type": x.atom_type,
        "content_json": x.content_json,
        "niche": x.niche,
        "audience_segment_id": str(x.audience_segment_id) if x.audience_segment_id else None,
        "platform": x.platform,
        "monetization_type": x.monetization_type,
        "account_type": x.account_type,
        "funnel_stage": x.funnel_stage,
        "performance_summary_json": x.performance_summary_json,
        "reuse_recommendations_json": x.reuse_recommendations_json,
        "originality_caution_score": x.originality_caution_score,
        "confidence_score": x.confidence_score,
        "is_active": x.is_active,
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _link_dict(x: CreativeMemoryLink) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "atom_id": str(x.atom_id),
        "linked_scope_type": x.linked_scope_type,
        "linked_scope_id": str(x.linked_scope_id),
        "relationship_type": x.relationship_type,
    }


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


async def get_creative_memory(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(CreativeMemoryAtom)
                .where(
                    CreativeMemoryAtom.brand_id == brand_id,
                    CreativeMemoryAtom.is_active.is_(True),
                )
                .order_by(CreativeMemoryAtom.confidence_score.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_atom_dict(r) for r in rows]


async def get_creative_memory_links(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(CreativeMemoryLink)
                .where(CreativeMemoryLink.brand_id == brand_id)
                .order_by(CreativeMemoryLink.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_link_dict(r) for r in rows]
