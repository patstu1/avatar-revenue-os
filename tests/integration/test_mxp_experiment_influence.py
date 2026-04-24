"""Integration: experiment outcomes + cross-module influence (Postgres via TEST_DATABASE_URL)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from apps.api.services import deal_desk_service, experiment_decision_service
from packages.db.enums import MonetizationMethod
from packages.db.models.audience_state import AudienceStateReport
from packages.db.models.contribution import ContributionReport
from packages.db.models.core import Brand, Organization
from packages.db.models.deal_desk import DealDeskRecommendation
from packages.db.models.experiment_decisions import ExperimentOutcome, ExperimentOutcomeAction
from packages.db.models.market_timing import MarketTimingReport
from packages.db.models.offers import Offer


@pytest.mark.asyncio
async def test_experiment_recompute_persists_outcomes(db_session):
    org = Organization(name="Exp Org", slug="exp-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        name="Exp Brand",
        slug=f"exp-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        niche="tech",
    )
    db_session.add(brand)
    await db_session.flush()
    db_session.add(
        Offer(
            brand_id=brand.id,
            name="Test Offer",
            monetization_method=MonetizationMethod.AFFILIATE,
            conversion_rate=0.04,
            epc=2.0,
            average_order_value=99.0,
            is_active=True,
        )
    )
    await db_session.commit()

    out = await experiment_decision_service.recompute_experiment_decisions(db_session, brand.id)
    await db_session.commit()
    assert out["experiment_decisions"] >= 1
    assert out["experiment_outcomes"] >= 1
    assert out.get("experiment_outcome_actions", 0) >= 1

    rows = (
        (await db_session.execute(select(ExperimentOutcome).where(ExperimentOutcome.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(rows) >= 1
    assert rows[0].experiment_decision_id
    assert rows[0].confidence_score is not None
    assert rows[0].observation_source == "synthetic_proxy"

    actions = (
        (
            await db_session.execute(
                select(ExperimentOutcomeAction).where(ExperimentOutcomeAction.brand_id == brand.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) >= 1
    assert actions[0].execution_status == "pending_operator"
    payload = actions[0].structured_payload_json or {}
    assert "recommended_operator_steps" in payload


@pytest.mark.asyncio
async def test_deal_desk_reads_audience_state_and_market_timing(db_session):
    org = Organization(name="DD Inf Org", slug="dd-inf-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        name="DD Inf Brand",
        slug=f"ddinf-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        niche="finance",
    )
    db_session.add(brand)
    await db_session.flush()
    db_session.add(
        AudienceStateReport(
            brand_id=brand.id,
            state_name="evaluating",
            state_score=0.82,
            best_next_action="nurture",
            confidence_score=0.7,
        )
    )
    db_session.add(
        MarketTimingReport(
            brand_id=brand.id,
            market_category="general",
            timing_score=0.75,
            recommendation="surge",
            active_window="Q1",
        )
    )
    db_session.add(
        Offer(
            brand_id=brand.id,
            name="O1",
            monetization_method=MonetizationMethod.AFFILIATE,
            conversion_rate=0.03,
            epc=1.0,
            average_order_value=50.0,
            is_active=True,
        )
    )
    await db_session.commit()

    await deal_desk_service.recompute_deal_desk(db_session, brand.id)
    await db_session.commit()

    rec = (
        await db_session.execute(
            select(DealDeskRecommendation).where(DealDeskRecommendation.brand_id == brand.id).limit(1)
        )
    ).scalar_one_or_none()
    assert rec is not None
    expl = rec.explanation_json or {}
    assert expl.get("cross_module_influence") is not None
    assert expl["cross_module_influence"].get("audience_state_lead_modifier") is not None


@pytest.mark.asyncio
async def test_experiment_recompute_applies_market_timing_influence(db_session):
    org = Organization(name="MT Exp Org", slug="mt-exp-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        name="MT Exp Brand",
        slug=f"mte-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        niche="tech",
    )
    db_session.add(brand)
    await db_session.flush()
    db_session.add(
        MarketTimingReport(
            brand_id=brand.id,
            market_category="general",
            timing_score=0.95,
            recommendation="surge",
            active_window="Q1",
        )
    )
    db_session.add(
        Offer(
            brand_id=brand.id,
            name="MT Offer",
            monetization_method=MonetizationMethod.AFFILIATE,
            conversion_rate=0.04,
            epc=2.0,
            average_order_value=99.0,
            is_active=True,
        )
    )
    await db_session.commit()

    out = await experiment_decision_service.recompute_experiment_decisions(db_session, brand.id)
    await db_session.commit()
    assert out.get("market_timing_influence", {}).get("applied") is True


@pytest.mark.asyncio
async def test_contribution_report_adjusts_deal_desk_lead_quality(db_session):
    org = Organization(name="Contrib Org", slug="contrib-org")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        name="Contrib Brand",
        slug=f"contrib-{uuid.uuid4().hex[:8]}",
        organization_id=org.id,
        niche="saas",
    )
    db_session.add(brand)
    await db_session.flush()
    offer = Offer(
        brand_id=brand.id,
        name="Scoped Offer",
        monetization_method=MonetizationMethod.AFFILIATE,
        conversion_rate=0.02,
        epc=1.0,
        average_order_value=80.0,
        is_active=True,
    )
    db_session.add(offer)
    await db_session.commit()

    await deal_desk_service.recompute_deal_desk(db_session, brand.id)
    await db_session.commit()
    rec1 = (
        await db_session.execute(
            select(DealDeskRecommendation).where(
                DealDeskRecommendation.brand_id == brand.id,
                DealDeskRecommendation.scope_type == "offer",
            )
        )
    ).scalar_one_or_none()
    assert rec1 is not None
    lq1 = (rec1.explanation_json or {}).get("adjusted_inputs", {}).get("lead_quality")

    db_session.add(
        ContributionReport(
            brand_id=brand.id,
            attribution_model="first_touch",
            scope_type="offer",
            scope_id=offer.id,
            estimated_contribution_value=500.0,
            contribution_score=0.95,
            confidence_score=0.8,
        )
    )
    await db_session.commit()

    await deal_desk_service.recompute_deal_desk(db_session, brand.id)
    await db_session.commit()
    rec2 = (
        await db_session.execute(
            select(DealDeskRecommendation).where(
                DealDeskRecommendation.brand_id == brand.id,
                DealDeskRecommendation.scope_type == "offer",
            )
        )
    ).scalar_one_or_none()
    assert rec2 is not None
    adj = rec2.explanation_json or {}
    assert adj.get("adjusted_inputs", {}).get("contribution_score_applied") == 0.95
    lq2 = adj.get("adjusted_inputs", {}).get("lead_quality")
    assert lq2 is not None and lq1 is not None
    assert lq2 > lq1
