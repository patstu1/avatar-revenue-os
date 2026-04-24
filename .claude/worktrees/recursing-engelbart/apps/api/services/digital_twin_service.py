"""Digital Twin Service — run simulations, persist scenarios, recommend."""
from __future__ import annotations
import uuid
from typing import Any
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.account_state_intel import AccountStateReport
from packages.db.models.campaigns import Campaign
from packages.db.models.offer_lab import OfferLabOffer
from packages.db.models.promote_winner import PWExperimentWinner
from packages.db.models.digital_twin import (
    SimulationRun, SimulationScenario, SimulationAssumption,
    SimulationOutcome, SimulationRecommendation,
)
from packages.scoring.digital_twin_engine import generate_scenarios, compare_options, build_recommendation, estimate_outcome


async def run_simulation(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(SimulationRecommendation).where(SimulationRecommendation.brand_id == brand_id))
    await db.execute(delete(SimulationOutcome).where(SimulationOutcome.scenario_id.in_(
        select(SimulationScenario.id).join(SimulationRun).where(SimulationRun.brand_id == brand_id)
    )))
    await db.execute(delete(SimulationAssumption).where(SimulationAssumption.scenario_id.in_(
        select(SimulationScenario.id).join(SimulationRun).where(SimulationRun.brand_id == brand_id)
    )))
    await db.execute(delete(SimulationScenario).where(SimulationScenario.run_id.in_(
        select(SimulationRun.id).where(SimulationRun.brand_id == brand_id)
    )))
    await db.execute(delete(SimulationRun).where(SimulationRun.brand_id == brand_id))

    system_state = await _gather_state(db, brand_id)
    raw_scenarios = generate_scenarios(system_state)

    run = SimulationRun(brand_id=brand_id, run_name=f"Auto simulation for brand", scenario_count=len(raw_scenarios) * 2)
    db.add(run); await db.flush()

    best_id = None
    best_score = -1
    recs = []

    for s in raw_scenarios:
        comparison = compare_options(s["option_a"], s["option_b"])

        for opt_key, opt_data, outcome_data, is_winner in [
            ("a", s["option_a"], comparison["option_a_outcome"], comparison["winner"] == "a"),
            ("b", s["option_b"], comparison["option_b_outcome"], comparison["winner"] == "b"),
        ]:
            sc = SimulationScenario(
                run_id=run.id, scenario_type=s["scenario_type"],
                option_label=opt_data["label"], compared_to=s["option_b"]["label"] if opt_key == "a" else s["option_a"]["label"],
                expected_upside=float(opt_data["upside"]), expected_cost=float(opt_data["cost"]),
                expected_risk=float(opt_data["risk"]), confidence=outcome_data["confidence"],
                time_to_signal_days=outcome_data["time_to_signal_days"],
                is_recommended=is_winner,
                explanation=comparison["explanation"] if is_winner else None,
            )
            db.add(sc); await db.flush()

            db.add(SimulationOutcome(scenario_id=sc.id, metric="risk_adjusted_profit", predicted_value=outcome_data["risk_adjusted_profit"], confidence=outcome_data["confidence"], risk_adjusted_value=outcome_data["risk_adjusted_profit"]))
            db.add(SimulationAssumption(scenario_id=sc.id, assumption_key="base_upside", assumption_value=str(opt_data["upside"]), confidence=outcome_data["confidence"]))

            score = outcome_data["risk_adjusted_profit"] * outcome_data["confidence"]
            if is_winner and score > best_score:
                best_score = score
                best_id = sc.id

        rec = build_recommendation(s)
        recs.append(rec)

    run.best_scenario_id = best_id
    run.total_expected_upside = sum(r["expected_profit_delta"] for r in recs)
    run.summary = f"{len(raw_scenarios)} simulations, {len(recs)} recommendations"

    for r in recs:
        db.add(SimulationRecommendation(run_id=run.id, brand_id=brand_id, **r))

    await db.flush()
    return {"rows_processed": len(raw_scenarios) * 2, "recommendations": len(recs), "status": "completed"}


async def _gather_state(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    state: dict[str, Any] = {"scaling_accounts": [], "experiment_winners": [], "offers": [], "weak_campaigns": []}

    acct_states = list((await db.execute(select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True)))).scalars().all())
    for s in acct_states:
        if s.current_state in ("scaling", "monetizing"):
            state["scaling_accounts"].append({"id": str(s.account_id), "name": str(s.account_id)[:8], "state": s.current_state})

    winners = list((await db.execute(select(PWExperimentWinner).where(PWExperimentWinner.brand_id == brand_id).limit(5))).scalars().all())
    for w in winners:
        state["experiment_winners"].append({"id": str(w.id), "confidence": float(w.confidence)})

    offers = list((await db.execute(select(OfferLabOffer).where(OfferLabOffer.brand_id == brand_id, OfferLabOffer.is_active.is_(True)).order_by(OfferLabOffer.rank_score).limit(5))).scalars().all())
    for o in offers:
        state["offers"].append({"id": str(o.id), "rank_score": float(o.rank_score), "name": o.offer_name})

    camps = list((await db.execute(select(Campaign).where(Campaign.brand_id == brand_id, Campaign.is_active.is_(True), Campaign.confidence < 0.4).limit(3))).scalars().all())
    for c in camps:
        state["weak_campaigns"].append({"id": str(c.id), "name": c.campaign_name, "confidence": float(c.confidence)})

    return state


async def list_runs(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(SimulationRun).where(SimulationRun.brand_id == brand_id).order_by(SimulationRun.created_at.desc()).limit(10))).scalars().all())

async def list_scenarios(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(SimulationScenario).join(SimulationRun).where(SimulationRun.brand_id == brand_id, SimulationScenario.is_active.is_(True)).order_by(SimulationScenario.expected_upside.desc()))).scalars().all())

async def list_recommendations(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(SimulationRecommendation).where(SimulationRecommendation.brand_id == brand_id, SimulationRecommendation.is_active.is_(True)).order_by(SimulationRecommendation.expected_profit_delta.desc()))).scalars().all())

async def get_top_recommendations(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Downstream: top recommendations for copilot/allocator."""
    recs = list((await db.execute(select(SimulationRecommendation).where(SimulationRecommendation.brand_id == brand_id, SimulationRecommendation.is_active.is_(True)).order_by(SimulationRecommendation.expected_profit_delta.desc()).limit(3))).scalars().all())
    return [{"type": r.scenario_type, "action": r.recommended_action, "delta": r.expected_profit_delta, "confidence": r.confidence} for r in recs]
