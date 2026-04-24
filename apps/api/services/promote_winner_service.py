"""Promote-Winner Service — create, observe, detect, promote, suppress, decay."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory
from packages.db.models.promote_winner import (
    ActiveExperiment,
    PromotedWinnerRule,
    PWExperimentLoser,
    PWExperimentObservation,
    PWExperimentVariant,
    PWExperimentWinner,
)
from packages.scoring.pattern_memory_engine import _sig
from packages.scoring.promote_winner_engine import (
    build_promotion_rules,
    check_decay_retest,
    detect_winner,
)
from packages.scoring.promote_winner_engine import (
    create_experiment as engine_create,
)


async def create_experiment(
    db: AsyncSession,
    brand_id: uuid.UUID,
    data: dict[str, Any],
) -> ActiveExperiment:
    spec = engine_create(
        data["tested_variable"],
        data["variant_configs"],
        hypothesis=data.get("hypothesis", ""),
        primary_metric=data.get("primary_metric", "engagement_rate"),
        min_sample_size=data.get("min_sample_size", 30),
        confidence_threshold=data.get("confidence_threshold", 0.90),
        platform=data.get("target_platform"),
        niche=data.get("target_niche"),
    )
    exp = ActiveExperiment(
        brand_id=brand_id,
        experiment_name=data["experiment_name"],
        hypothesis=spec["hypothesis"],
        tested_variable=spec["tested_variable"],
        target_platform=spec.get("platform"),
        target_offer_id=data.get("target_offer_id"),
        target_niche=spec.get("niche"),
        primary_metric=spec["primary_metric"],
        min_sample_size=spec["min_sample_size"],
        confidence_threshold=spec["confidence_threshold"],
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(exp)
    await db.flush()

    for vs in spec["variants"]:
        db.add(
            PWExperimentVariant(
                experiment_id=exp.id,
                variant_name=vs["variant_name"],
                variant_config=vs["variant_config"],
                is_control=vs["is_control"],
            )
        )
    await db.flush()
    return exp


async def add_observation(
    db: AsyncSession,
    experiment_id: uuid.UUID,
    variant_id: uuid.UUID,
    metric_name: str,
    metric_value: float,
    content_item_id: uuid.UUID = None,
) -> None:
    db.add(
        PWExperimentObservation(
            experiment_id=experiment_id,
            variant_id=variant_id,
            content_item_id=content_item_id,
            metric_name=metric_name,
            metric_value=metric_value,
        )
    )
    variant = (
        await db.execute(select(PWExperimentVariant).where(PWExperimentVariant.id == variant_id))
    ).scalar_one_or_none()
    if variant:
        variant.sample_count = (variant.sample_count or 0) + 1
        if (
            metric_name
            == (
                await db.execute(select(ActiveExperiment.primary_metric).where(ActiveExperiment.id == experiment_id))
            ).scalar()
        ):
            obs = (
                await db.execute(
                    select(func.avg(PWExperimentObservation.metric_value)).where(
                        PWExperimentObservation.variant_id == variant_id,
                        PWExperimentObservation.metric_name == metric_name,
                    )
                )
            ).scalar() or 0
            variant.primary_metric_value = float(obs)
    await db.flush()


async def evaluate_experiment(
    db: AsyncSession,
    experiment_id: uuid.UUID,
) -> dict[str, Any]:
    exp = (await db.execute(select(ActiveExperiment).where(ActiveExperiment.id == experiment_id))).scalar_one_or_none()
    if not exp:
        return {"status": "not_found"}

    variants = list(
        (await db.execute(select(PWExperimentVariant).where(PWExperimentVariant.experiment_id == experiment_id)))
        .scalars()
        .all()
    )

    v_dicts = [
        {
            "id": str(v.id),
            "variant_name": v.variant_name,
            "variant_config": v.variant_config or {},
            "is_control": v.is_control,
            "sample_count": v.sample_count,
            "primary_metric_value": float(v.primary_metric_value),
            "is_active": v.is_active,
        }
        for v in variants
    ]

    result = detect_winner(v_dicts, exp.min_sample_size, exp.confidence_threshold)

    if result["status"] == "winner_found":
        winner_data = result["winner"]
        loser_data = result["losers"]

        await db.execute(delete(PWExperimentWinner).where(PWExperimentWinner.experiment_id == experiment_id))
        await db.execute(delete(PWExperimentLoser).where(PWExperimentLoser.experiment_id == experiment_id))
        await db.execute(delete(PromotedWinnerRule).where(PromotedWinnerRule.experiment_id == experiment_id))

        w = PWExperimentWinner(
            experiment_id=experiment_id,
            variant_id=uuid.UUID(winner_data["id"]),
            brand_id=exp.brand_id,
            win_margin=result["win_margin"],
            confidence=result["confidence"],
            sample_size=winner_data.get("sample_count", 0),
            promoted=True,
            explanation=f"Winner: {winner_data['variant_name']} with margin {result['win_margin']:.1%}",
        )
        db.add(w)
        await db.flush()

        exp_dict = {"tested_variable": exp.tested_variable, "platform": exp.target_platform}
        promo_rules = build_promotion_rules(exp_dict, winner_data, result["win_margin"], result["confidence"])
        for rule in promo_rules:
            db.add(
                PromotedWinnerRule(
                    brand_id=exp.brand_id,
                    experiment_id=experiment_id,
                    winner_id=w.id,
                    rule_type=rule["rule_type"],
                    rule_key=rule["rule_key"],
                    rule_value=rule.get("rule_value"),
                    target_platform=rule.get("target_platform"),
                    weight_boost=rule["weight_boost"],
                    explanation=rule["explanation"],
                )
            )

        for ld in loser_data:
            db.add(
                PWExperimentLoser(
                    experiment_id=experiment_id,
                    variant_id=uuid.UUID(ld["id"]),
                    brand_id=exp.brand_id,
                    loss_margin=abs(result["win_margin"]),
                    suppressed=True,
                    explanation=f"Lost to {winner_data['variant_name']}",
                )
            )

        sig = _sig(exp.tested_variable, winner_data["variant_name"], exp.target_platform or "", "")
        existing_pm = (
            await db.execute(
                select(WinningPatternMemory).where(
                    WinningPatternMemory.brand_id == exp.brand_id,
                    WinningPatternMemory.pattern_signature == sig,
                )
            )
        ).scalar_one_or_none()
        if not existing_pm:
            db.add(
                WinningPatternMemory(
                    brand_id=exp.brand_id,
                    pattern_type=exp.tested_variable,
                    pattern_name=winner_data["variant_name"],
                    pattern_signature=sig,
                    performance_band="strong",
                    confidence=result["confidence"],
                    win_score=min(1.0, 0.6 + result["win_margin"]),
                    explanation=f"Promoted from experiment {experiment_id}",
                    evidence_json={"experiment_id": str(experiment_id), "margin": result["win_margin"]},
                )
            )

        for ld in loser_data:
            lsig = _sig(exp.tested_variable, ld["variant_name"], exp.target_platform or "", "")
            existing_lp = (
                await db.execute(
                    select(LosingPatternMemory).where(
                        LosingPatternMemory.brand_id == exp.brand_id,
                        LosingPatternMemory.pattern_signature == lsig,
                    )
                )
            ).scalar_one_or_none()
            if not existing_lp:
                db.add(
                    LosingPatternMemory(
                        brand_id=exp.brand_id,
                        pattern_type=exp.tested_variable,
                        pattern_name=ld["variant_name"],
                        pattern_signature=lsig,
                        fail_score=abs(result["win_margin"]),
                        suppress_reason=f"Lost in experiment {experiment_id}",
                        evidence_json={"experiment_id": str(experiment_id)},
                    )
                )

        exp.status = "completed"
        exp.ended_at = datetime.now(timezone.utc)
        await db.flush()

    return result


async def run_decay_check(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Check all promoted winners for decay. Returns retests needed."""
    rules = list(
        (
            await db.execute(
                select(PromotedWinnerRule).where(
                    PromotedWinnerRule.brand_id == brand_id,
                    PromotedWinnerRule.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    retests = 0
    for rule in rules:
        winner = (
            await db.execute(select(PWExperimentWinner).where(PWExperimentWinner.id == rule.winner_id))
        ).scalar_one_or_none()
        if not winner:
            continue
        age = (
            (datetime.now(timezone.utc) - winner.created_at.replace(tzinfo=timezone.utc)).days
            if winner.created_at
            else 0
        )
        decay = check_decay_retest(
            age, float(winner.confidence), float(winner.win_margin * 0.9), float(winner.win_margin)
        )
        if decay["needs_retest"]:
            rule.is_active = False
            retests += 1

    return {"retests_needed": retests, "rules_checked": len(rules), "status": "completed"}


async def list_active_experiments(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(ActiveExperiment)
                .where(ActiveExperiment.brand_id == brand_id)
                .order_by(ActiveExperiment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_winners(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(PWExperimentWinner)
                .where(PWExperimentWinner.brand_id == brand_id)
                .order_by(PWExperimentWinner.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_losers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(PWExperimentLoser)
                .where(PWExperimentLoser.brand_id == brand_id)
                .order_by(PWExperimentLoser.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_promoted_rules(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(PromotedWinnerRule)
                .where(PromotedWinnerRule.brand_id == brand_id, PromotedWinnerRule.is_active.is_(True))
                .order_by(PromotedWinnerRule.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_promoted_rules_for_brief(
    db: AsyncSession, brand_id: uuid.UUID, platform: str = None
) -> list[dict[str, Any]]:
    """Return active promotion rules suitable for injecting into content briefs."""
    q = select(PromotedWinnerRule).where(
        PromotedWinnerRule.brand_id == brand_id,
        PromotedWinnerRule.is_active.is_(True),
    )
    if platform:
        q = q.where((PromotedWinnerRule.target_platform == platform) | (PromotedWinnerRule.target_platform.is_(None)))
    rows = list((await db.execute(q)).scalars().all())
    return [
        {"rule_type": r.rule_type, "rule_key": r.rule_key, "rule_value": r.rule_value, "weight_boost": r.weight_boost}
        for r in rows
    ]
