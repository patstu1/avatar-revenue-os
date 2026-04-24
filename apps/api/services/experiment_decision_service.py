"""Experiment decision service — prioritise tests, persist outcomes, close the loop."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.experiment_decisions import (
    ExperimentDecision,
    ExperimentOutcome,
    ExperimentOutcomeAction,
)
from packages.db.models.market_timing import MarketTimingReport
from packages.db.models.offer_lifecycle import OfferLifecycleReport
from packages.db.models.offers import Offer
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.experiment_decision_engine import (
    EXP_DEC,
    apply_prior_scope_signals,
    evaluate_experiment_outcome,
    prioritize_experiment_candidates,
)


def _strip_meta(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != EXP_DEC}


async def _load_prior_scope_signals(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Snapshot outcome history keyed by scope (survives decision row refresh)."""
    stmt = (
        select(ExperimentOutcome, ExperimentDecision)
        .join(ExperimentDecision, ExperimentOutcome.experiment_decision_id == ExperimentDecision.id)
        .where(ExperimentOutcome.brand_id == brand_id)
        .order_by(ExperimentOutcome.created_at.desc())
        .limit(200)
    )
    rows = (await db.execute(stmt)).all()
    seen: set[tuple[str, str | None]] = set()
    signals: list[dict[str, Any]] = []
    for out, dec in rows:
        st = dec.target_scope_type
        sid = str(dec.target_scope_id) if dec.target_scope_id else None
        key = (st, sid)
        if key in seen:
            continue
        seen.add(key)
        signals.append(
            {
                "target_scope_type": st,
                "target_scope_id": sid,
                "outcome_type": out.outcome_type,
                "observed_uplift": float(out.observed_uplift),
            }
        )
    return signals


async def _load_offer_lifecycle_map(db: AsyncSession, brand_id: uuid.UUID) -> dict[uuid.UUID, tuple[str, float]]:
    rows = list(
        (
            await db.execute(
                select(OfferLifecycleReport).where(
                    OfferLifecycleReport.brand_id == brand_id,
                    OfferLifecycleReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return {r.offer_id: (r.lifecycle_state, float(r.health_score or 0.0)) for r in rows}


async def _load_latest_market_timing_score(db: AsyncSession, brand_id: uuid.UUID) -> float | None:
    row = (
        await db.execute(
            select(MarketTimingReport)
            .where(
                MarketTimingReport.brand_id == brand_id,
                MarketTimingReport.is_active.is_(True),
            )
            .order_by(MarketTimingReport.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return float(row.timing_score or 0.0)


def apply_market_timing_to_experiment_candidates(
    experiments: list[dict[str, Any]], timing_score: float | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Raise/lower expected_upside from market timing (cross-module influence)."""
    if timing_score is None:
        return experiments, {"applied": False}
    ts = max(0.0, min(1.0, float(timing_score)))
    mult = 0.92 + 0.16 * ts
    for e in experiments:
        e["expected_upside"] = min(1.0, float(e.get("expected_upside", 0)) * mult)
    return experiments, {
        "applied": True,
        "timing_score": ts,
        "expected_upside_multiplier": round(mult, 4),
    }


def _lifecycle_skew_for_offer(
    offer_id: uuid.UUID, lc_map: dict[uuid.UUID, tuple[str, float]]
) -> tuple[float, str | None]:
    """Returns (multiplier for expected_upside, note)."""
    if offer_id not in lc_map:
        return 1.0, None
    state, health = lc_map[offer_id]
    s = state.lower()
    if s in ("sunset", "fatigued", "deprecated"):
        return 0.35, f"offer_lifecycle:{state}"
    if s == "active" and health >= 0.72:
        return 1.12, "offer_lifecycle:active_healthy"
    if health < 0.35:
        return 0.55, "offer_lifecycle:low_health"
    return 1.0, None


def _synthetic_observed_data(
    decision: ExperimentDecision,
    offers_by_id: dict[uuid.UUID, Offer],
    content_by_id: dict[uuid.UUID, ContentItem],
    perf_by_content: dict[uuid.UUID, float],
) -> dict[str, Any]:
    """Proxy variant data from persisted offers/content/metrics (rules-based)."""
    if decision.target_scope_type == "offer" and decision.target_scope_id:
        offer = offers_by_id.get(decision.target_scope_id)
        if offer:
            cr = max(0.005, float(offer.conversion_rate or 0.02))
            va = uuid.uuid4()
            vb = uuid.uuid4()
            return {
                "variants": [
                    {"variant_id": str(va), "conversion_rate": cr, "sample_size": 520},
                    {"variant_id": str(vb), "conversion_rate": cr * 0.90, "sample_size": 505},
                ],
                "baseline_conversion_rate": cr * 0.93,
                "days_running": 21,
            }
    if decision.target_scope_type == "content_item" and decision.target_scope_id:
        content_by_id.get(decision.target_scope_id)
        eng = perf_by_content.get(decision.target_scope_id, 0.04)
        cr = max(0.005, min(0.25, eng * 0.6))
        va = uuid.uuid4()
        vb = uuid.uuid4()
        return {
            "variants": [
                {"variant_id": str(va), "conversion_rate": cr, "sample_size": 300},
                {"variant_id": str(vb), "conversion_rate": cr * 0.92, "sample_size": 290},
            ],
            "baseline_conversion_rate": cr * 0.94,
            "days_running": 14,
        }
    cr = 0.02
    va = uuid.uuid4()
    vb = uuid.uuid4()
    return {
        "variants": [
            {"variant_id": str(va), "conversion_rate": cr, "sample_size": 200},
            {"variant_id": str(vb), "conversion_rate": cr * 0.95, "sample_size": 200},
        ],
        "baseline_conversion_rate": cr * 0.96,
        "days_running": 10,
    }


def _experiment_dict_from_decision(dec: ExperimentDecision) -> dict[str, Any]:
    return {
        "experiment_type": dec.experiment_type,
        "target_scope_type": dec.target_scope_type,
        "target_scope_id": str(dec.target_scope_id) if dec.target_scope_id else None,
        "hypothesis": dec.hypothesis or "",
    }


def _downstream_action_payload(
    r: dict[str, Any],
    dec: ExperimentDecision,
    wid: uuid.UUID | None,
    losers: list[Any],
    observed: dict[str, Any],
) -> dict[str, Any]:
    next_act = (r.get("recommended_next_action") or "").strip() or None
    steps = []
    if next_act:
        steps.append(next_act)
    steps.append(
        "Apply promotion/suppression in your ad or content stack using the winner variant; "
        "this queue row is the execution handoff (external tools not wired automatically)."
    )
    return {
        "outcome_type": r.get("outcome_type"),
        "winner_variant_id": str(wid) if wid else None,
        "loser_variant_ids": [str(x) for x in losers],
        "recommended_next_action": next_act,
        "recommended_operator_steps": steps,
        "observation_source": "synthetic_proxy",
        "scope": {
            "experiment_type": dec.experiment_type,
            "target_scope_type": dec.target_scope_type,
            "target_scope_id": str(dec.target_scope_id) if dec.target_scope_id else None,
        },
        "synthetic_observed_snapshot": observed,
    }


async def _persist_outcomes_for_decisions(
    db: AsyncSession,
    brand_id: uuid.UUID,
    decisions: list[ExperimentDecision],
    offers_by_id: dict[uuid.UUID, Offer],
    content_by_id: dict[uuid.UUID, ContentItem],
    perf_by_content: dict[uuid.UUID, float],
) -> tuple[int, int]:
    """Returns (outcome_count, outcome_action_count)."""
    oc = 0
    ac = 0
    for dec in decisions:
        exp_d = _experiment_dict_from_decision(dec)
        observed = _synthetic_observed_data(dec, offers_by_id, content_by_id, perf_by_content)
        raw = evaluate_experiment_outcome(exp_d, observed)
        r = _strip_meta(raw)
        losers = r.get("loser_variant_ids") or []
        winner = r.get("winner_variant_id")
        try:
            wid = uuid.UUID(str(winner)) if winner else None
        except (ValueError, TypeError):
            wid = None
        outcome_type = str(r.get("outcome_type", "inconclusive"))
        eo = ExperimentOutcome(
            brand_id=brand_id,
            experiment_decision_id=dec.id,
            observation_source="synthetic_proxy",
            outcome_type=outcome_type,
            winner_variant_id=wid,
            loser_variant_ids_json={"variant_ids": [str(x) for x in losers]},
            confidence_score=float(r.get("confidence", 0.0)),
            observed_uplift=float(r.get("observed_uplift", 0.0)),
            recommended_next_action=(r.get("recommended_next_action") or "")[:255],
            explanation_json={
                "explanation": r.get("explanation", ""),
                "data_boundary": {
                    "observation_source": "synthetic_proxy",
                    "meaning": (
                        "Uplift, variants, and confidence are derived from persisted offers, content, "
                        "and performance metrics using rules-based proxy logic — not a live A/B "
                        "platform feed. Treat as planning signal until live_import observations exist."
                    ),
                },
                "scope_snapshot": {
                    "experiment_type": dec.experiment_type,
                    "target_scope_type": dec.target_scope_type,
                    "target_scope_id": str(dec.target_scope_id) if dec.target_scope_id else None,
                },
                "synthetic_observed": observed,
            },
        )
        db.add(eo)
        await db.flush()

        payload = _downstream_action_payload(r, dec, wid, losers, observed)
        db.add(
            ExperimentOutcomeAction(
                brand_id=brand_id,
                experiment_outcome_id=eo.id,
                action_kind=outcome_type,
                execution_status="pending_operator",
                structured_payload_json=payload,
                operator_note=(
                    "Synthetic/proxy observation — execute in external ads/ops or manual workflow; "
                    "not auto-applied to channels."
                ),
            )
        )

        if outcome_type in ("winner_found", "promote") and wid:
            try:
                from packages.db.models.pattern_memory import WinningPatternMemory
                from packages.scoring.pattern_memory_engine import _sig

                exp_type = dec.experiment_type or "experiment"
                variant_name = str(wid)[:8]
                sig = _sig("experiment_winner", exp_type, "", "")
                existing = (
                    await db.execute(
                        select(WinningPatternMemory).where(
                            WinningPatternMemory.brand_id == brand_id,
                            WinningPatternMemory.pattern_signature == sig,
                        )
                    )
                ).scalar_one_or_none()
                if not existing:
                    db.add(
                        WinningPatternMemory(
                            brand_id=brand_id,
                            pattern_type=exp_type,
                            pattern_name=f"experiment_winner_{variant_name}",
                            pattern_signature=sig,
                            performance_band="strong",
                            confidence=float(r.get("confidence", 0.5)),
                            win_score=min(1.0, 0.6 + float(r.get("observed_uplift", 0))),
                            explanation=f"Promoted from experiment {dec.id}",
                            evidence_json={"experiment_id": str(dec.id), "uplift": float(r.get("observed_uplift", 0))},
                        )
                    )
            except Exception:
                logger.debug("experiment_winner_pattern_promotion_failed", exc_info=True)

        oc += 1
        ac += 1
    await db.flush()
    return oc, ac


# ---------------------------------------------------------------------------
# Recompute — decisions + outcomes (single loop)
# ---------------------------------------------------------------------------


async def recompute_experiment_decisions(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    prior_scope_signals = await _load_prior_scope_signals(db, brand_id)
    lifecycle_map = await _load_offer_lifecycle_map(db, brand_id)

    await db.execute(delete(ExperimentOutcome).where(ExperimentOutcome.brand_id == brand_id))
    await db.execute(
        delete(ExperimentDecision).where(
            ExperimentDecision.brand_id == brand_id,
            ExperimentDecision.is_active.is_(True),
        )
    )

    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    offers_by_id = {o.id: o for o in offers}

    content_items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(100))).scalars().all()
    )
    content_by_id = {ci.id: ci for ci in content_items}

    perf_rows = (
        await db.execute(
            select(PerformanceMetric.content_item_id, PerformanceMetric.engagement_rate).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).all()
    perf_by_content: dict[uuid.UUID, float] = {}
    for cid, eng in perf_rows:
        if cid:
            perf_by_content[cid] = float(eng or 0.0)

    experiments: list[dict[str, Any]] = []
    lifecycle_notes: list[str] = []

    for offer in offers:
        skew, note = _lifecycle_skew_for_offer(offer.id, lifecycle_map)
        base_up = 0.15 * skew
        if note:
            lifecycle_notes.append(note)
        experiments.append(
            {
                "experiment_type": "offer_variant",
                "target_scope_type": "offer",
                "target_scope_id": str(offer.id),
                "hypothesis": f"Testing variant of offer '{offer.name}' for conversion lift",
                "expected_upside": round(min(1.0, base_up), 4),
                "confidence_gap": 0.40,
                "age_days": 0,
            }
        )

    for ci in content_items[:20]:
        experiments.append(
            {
                "experiment_type": "content_format",
                "target_scope_type": "content_item",
                "target_scope_id": str(ci.id),
                "hypothesis": f"Testing format variation on '{ci.title}'",
                "expected_upside": 0.10,
                "confidence_gap": 0.50,
                "age_days": 0,
            }
        )

    try:
        from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory
        from packages.scoring.pattern_memory_engine import suggest_experiments_from_patterns

        win_rows = list(
            (
                await db.execute(
                    select(WinningPatternMemory).where(
                        WinningPatternMemory.brand_id == brand_id, WinningPatternMemory.is_active.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        lose_rows = list(
            (
                await db.execute(
                    select(LosingPatternMemory).where(
                        LosingPatternMemory.brand_id == brand_id, LosingPatternMemory.is_active.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_types = [e["experiment_type"] for e in experiments]
        suggestions = suggest_experiments_from_patterns(
            [
                {
                    "pattern_type": w.pattern_type,
                    "pattern_name": w.pattern_name,
                    "win_score": float(w.win_score),
                    "usage_count": w.usage_count,
                }
                for w in win_rows
            ],
            [
                {"pattern_type": l.pattern_type, "pattern_name": l.pattern_name, "fail_score": float(l.fail_score)}
                for l in lose_rows
            ],
            existing_types,
        )
        for s in suggestions[:10]:
            experiments.append(
                {
                    "experiment_type": s["tested_variable"],
                    "target_scope_type": "pattern_memory",
                    "target_scope_id": None,
                    "hypothesis": s["hypothesis"],
                    "expected_upside": 0.20 if s["priority"] == "high" else 0.12,
                    "confidence_gap": 0.60,
                    "age_days": 0,
                }
            )
    except Exception:
        logger.debug("pattern_based_experiment_suggestion_failed", exc_info=True)

    mt_score = await _load_latest_market_timing_score(db, brand_id)
    experiments, timing_influence = apply_market_timing_to_experiment_candidates(experiments, mt_score)
    experiments, signal_influence = apply_prior_scope_signals(experiments, prior_scope_signals)

    total_impressions = (
        await db.execute(select(PerformanceMetric.impressions).where(PerformanceMetric.brand_id == brand_id).limit(1))
    ).scalar()
    total_traffic = int(total_impressions or 1000)

    brand_context = {
        "brand_id": str(brand_id),
        "total_traffic": total_traffic,
        "risk_tolerance": 0.5,
        "prior_scope_signal_count": len(prior_scope_signals),
        "offer_lifecycle_skew_notes": lifecycle_notes[:20],
        "market_timing_influence": timing_influence,
    }

    scored = prioritize_experiment_candidates(experiments, brand_context)

    for item in scored:
        r = _strip_meta(item)
        scope_id = r.get("target_scope_id")
        merged_expl = {
            "explanation": r.get("explanation", ""),
            "downstream": {
                "prior_outcome_signals_applied": signal_influence.get("signals_applied", 0),
                "prior_influence_detail": signal_influence.get("by_scope", []),
                "offer_lifecycle_gates": lifecycle_notes[:10],
                "market_timing_influence": timing_influence,
            },
        }
        promo = r.get("promotion_rule")
        supp = r.get("suppression_rule")
        # Close the loop: fold latest outcome tendencies into rule hints
        if prior_scope_signals:
            merged_expl["downstream"]["promotion_suppression_hint"] = (
                "Historical outcomes adjust expected upside before scoring; "
                "promote/suppress rules remain engine defaults unless scope matched a prior signal."
            )

        db.add(
            ExperimentDecision(
                brand_id=brand_id,
                experiment_type=r.get("experiment_type", "unknown"),
                target_scope_type=r.get("target_scope_type", "unknown"),
                target_scope_id=uuid.UUID(scope_id) if scope_id else None,
                hypothesis=r.get("hypothesis", ""),
                expected_upside=float(r.get("expected_upside", 0)),
                confidence_gap=float(r.get("confidence_gap", 0)),
                priority_score=float(r.get("priority_score", 0)),
                recommended_allocation=float(r.get("recommended_allocation", 0.10)),
                promotion_rule_json=promo,
                suppression_rule_json=supp,
                explanation_json=merged_expl,
                status="proposed",
                is_active=True,
            )
        )

    await db.flush()

    decisions = list(
        (
            await db.execute(
                select(ExperimentDecision).where(
                    ExperimentDecision.brand_id == brand_id,
                    ExperimentDecision.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    oc, oa = await _persist_outcomes_for_decisions(
        db, brand_id, decisions, offers_by_id, content_by_id, perf_by_content
    )

    return {
        "experiment_decisions": len(scored),
        "experiment_outcomes": oc,
        "experiment_outcome_actions": oa,
        "prior_scope_signals_loaded": len(prior_scope_signals),
        "outcome_signal_influence": signal_influence,
        "market_timing_influence": timing_influence,
    }


async def recompute_experiment_outcomes_only(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Re-evaluate outcomes for current active decisions without rebuilding the decision set."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    decisions = list(
        (
            await db.execute(
                select(ExperimentDecision).where(
                    ExperimentDecision.brand_id == brand_id,
                    ExperimentDecision.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    if not decisions:
        return {"experiment_outcomes": 0, "experiment_outcome_actions": 0}

    offers = list((await db.execute(select(Offer).where(Offer.brand_id == brand_id))).scalars().all())
    offers_by_id = {o.id: o for o in offers}
    content_items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(200))).scalars().all()
    )
    content_by_id = {ci.id: ci for ci in content_items}
    perf_rows = (
        await db.execute(
            select(PerformanceMetric.content_item_id, PerformanceMetric.engagement_rate).where(
                PerformanceMetric.brand_id == brand_id
            )
        )
    ).all()
    perf_by_content = {cid: float(eng or 0.0) for cid, eng in perf_rows if cid}

    await db.execute(delete(ExperimentOutcome).where(ExperimentOutcome.brand_id == brand_id))
    oc, oa = await _persist_outcomes_for_decisions(
        db, brand_id, decisions, offers_by_id, content_by_id, perf_by_content
    )
    return {"experiment_outcomes": oc, "experiment_outcome_actions": oa}


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _ed_dict(x: ExperimentDecision) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "experiment_type": x.experiment_type,
        "target_scope_type": x.target_scope_type,
        "target_scope_id": str(x.target_scope_id) if x.target_scope_id else None,
        "hypothesis": x.hypothesis,
        "expected_upside": x.expected_upside,
        "confidence_gap": x.confidence_gap,
        "priority_score": x.priority_score,
        "recommended_allocation": x.recommended_allocation,
        "promotion_rule_json": x.promotion_rule_json,
        "suppression_rule_json": x.suppression_rule_json,
        "explanation_json": x.explanation_json,
        "status": x.status,
        "is_active": x.is_active,
        "data_source": "synthetic_proxy",
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _eo_dict(x: ExperimentOutcome) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "experiment_decision_id": str(x.experiment_decision_id),
        "observation_source": x.observation_source,
        "outcome_type": x.outcome_type,
        "winner_variant_id": str(x.winner_variant_id) if x.winner_variant_id else None,
        "loser_variant_ids_json": x.loser_variant_ids_json,
        "confidence_score": x.confidence_score,
        "observed_uplift": x.observed_uplift,
        "recommended_next_action": x.recommended_next_action,
        "explanation_json": x.explanation_json,
        "data_source": x.observation_source or "synthetic_proxy",
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


def _eoa_dict(x: ExperimentOutcomeAction) -> dict[str, Any]:
    return {
        "id": str(x.id),
        "brand_id": str(x.brand_id),
        "experiment_outcome_id": str(x.experiment_outcome_id),
        "action_kind": x.action_kind,
        "execution_status": x.execution_status,
        "structured_payload_json": x.structured_payload_json,
        "operator_note": x.operator_note,
        "data_source": "operator_queued",
        "created_at": x.created_at,
        "updated_at": x.updated_at,
    }


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


async def get_experiment_decisions(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ExperimentDecision)
                .where(
                    ExperimentDecision.brand_id == brand_id,
                    ExperimentDecision.is_active.is_(True),
                )
                .order_by(ExperimentDecision.priority_score.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_ed_dict(r) for r in rows]


async def get_experiment_outcomes(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ExperimentOutcome)
                .where(ExperimentOutcome.brand_id == brand_id)
                .order_by(ExperimentOutcome.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_eo_dict(r) for r in rows]


_VALID_EXECUTION_STATUSES = frozenset(
    {
        "pending_operator",
        "acknowledged",
        "in_progress",
        "completed",
        "rejected",
        "skipped",
    }
)


async def update_outcome_action_status(
    db: AsyncSession,
    brand_id: uuid.UUID,
    action_id: uuid.UUID,
    new_status: str,
    operator_note: str | None = None,
) -> dict[str, Any]:
    if new_status not in _VALID_EXECUTION_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'; valid: {sorted(_VALID_EXECUTION_STATUSES)}")
    row = (
        await db.execute(
            select(ExperimentOutcomeAction).where(
                ExperimentOutcomeAction.id == action_id,
                ExperimentOutcomeAction.brand_id == brand_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise ValueError("Outcome action not found")
    row.execution_status = new_status
    if operator_note is not None:
        row.operator_note = operator_note
    await db.flush()
    return _eoa_dict(row)


async def get_experiment_outcome_actions(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ExperimentOutcomeAction)
                .where(ExperimentOutcomeAction.brand_id == brand_id)
                .order_by(ExperimentOutcomeAction.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [_eoa_dict(r) for r in rows]
