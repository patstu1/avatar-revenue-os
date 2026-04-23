import uuid

import pytest
from sqlalchemy import select

from packages.db.models.core import Brand, Organization
from packages.db.models.offers import AudienceSegment, Offer, SponsorProfile
from packages.db.models.expansion_pack2_phase_c import (
    ReferralProgramRecommendation,
    CompetitiveGapReport,
    SponsorTarget,
    SponsorOutreachSequence,
    ProfitGuardrailReport,
)

pytestmark = pytest.mark.skipif(
    True,
    reason="Worker tests call Celery tasks that use the production session factory; they need a dedicated worker test harness",
)

from workers.revenue_ceiling_worker.tasks import (
    recompute_all_referral_program_recommendations,
    recompute_all_competitive_gap_reports,
    recompute_all_sponsor_targets,
    recompute_all_sponsor_outreach_sequences,
    recompute_all_profit_guardrail_reports,
)


@pytest.fixture
async def brand_with_offer(async_session):
    organization = Organization(name="Test Org", slug="ep2c-worker-test")
    async_session.add(organization)
    await async_session.flush()

    brand = Brand(name="Test Brand", slug="ep2c-w-brand", organization_id=organization.id)
    async_session.add(brand)
    await async_session.flush()

    offer = Offer(
        brand_id=brand.id,
        name="Test Offer",
        description="A test offer",
        monetization_method="affiliate",
        payout_amount=100.0,
        is_active=True,
    )
    async_session.add(offer)

    # Add some AudienceSegment data for testing referral recommendations
    high_value_segment = AudienceSegment(
        brand_id=brand.id,
        name="High-Value Loyal Customers",
        description="Customers with high loyalty and purchase value",
        estimated_size=1000,
        revenue_contribution=50000.0,
        conversion_rate=0.08, # loyalty_score proxy
        avg_ltv=500.0, # avg_purchase_value proxy
    )
    async_session.add(high_value_segment)

    new_customer_segment = AudienceSegment(
        brand_id=brand.id,
        name="New Engaged Customers",
        description="Recently acquired and engaged customers",
        estimated_size=2000,
        revenue_contribution=20000.0,
        conversion_rate=0.03, # loyalty_score proxy
        avg_ltv=100.0, # avg_purchase_value proxy
    )
    async_session.add(new_customer_segment)

    general_segment = AudienceSegment(
        brand_id=brand.id,
        name="General Audience",
        description="Broad audience segment",
        estimated_size=10000,
        revenue_contribution=75000.0,
        conversion_rate=0.02, # loyalty_score proxy
        avg_ltv=75.0, # avg_purchase_value proxy
    )
    async_session.add(general_segment)

    # Add some SponsorProfile data for testing sponsor target identification
    tech_sponsor = SponsorProfile(
        brand_id=brand.id,
        sponsor_name="TechCorp Solutions",
        industry="Technology",
        budget_range_min=100000.0,
        budget_range_max=500000.0,
        preferred_platforms=["YouTube", "Instagram"],
        preferred_content_types=["video", "tutorial"],
        contact_email="sponsors@techcorp.com",
    )
    async_session.add(tech_sponsor)

    fashion_sponsor = SponsorProfile(
        brand_id=brand.id,
        sponsor_name="FashionForward Brands",
        industry="Fashion",
        budget_range_min=50000.0,
        budget_range_max=200000.0,
        preferred_platforms=["Instagram", "TikTok"],
        preferred_content_types=["lifestyle", "hauls"],
        contact_email="partners@fashionforward.com",
    )
    async_session.add(fashion_sponsor)

    await async_session.commit()
    return brand, offer


@pytest.mark.asyncio
async def test_recompute_all_referral_program_recommendations_worker(async_session, brand_with_offer):
    brand, _ = brand_with_offer
    result = recompute_all_referral_program_recommendations()
    assert result["brands"] == 1
    assert result["rows"] == 1
    assert not result["errors"]

    recommendations = (await async_session.execute(select(ReferralProgramRecommendation).where(ReferralProgramRecommendation.brand_id == brand.id))).scalars().all()
    assert len(recommendations) == 1
    assert recommendations[0].brand_id == brand.id
    assert recommendations[0].customer_segment is not None
    assert recommendations[0].recommendation_type is not None
    assert recommendations[0].referral_bonus > 0
    assert recommendations[0].referred_bonus > 0
    assert recommendations[0].estimated_conversion_rate > 0
    assert recommendations[0].estimated_revenue_impact > 0
    assert recommendations[0].confidence > 0


@pytest.mark.asyncio
async def test_recompute_all_competitive_gap_reports_worker(async_session, brand_with_offer):
    brand, offer = brand_with_offer
    result = recompute_all_competitive_gap_reports()
    assert result["brands"] == 1
    assert result["rows"] == 1
    assert not result["errors"]

    reports = (await async_session.execute(select(CompetitiveGapReport).where(CompetitiveGapReport.brand_id == brand.id))).scalars().all()
    assert len(reports) == 1
    assert reports[0].brand_id == brand.id
    assert reports[0].gap_type in ("pricing_disadvantage", "feature_disadvantage", "customer_satisfaction_gap", "no_significant_gap")
    assert reports[0].severity in ("low", "medium", "high", "critical")
    assert reports[0].estimated_impact >= 0
    assert reports[0].confidence > 0
    assert reports[0].gap_description is not None


@pytest.mark.asyncio
async def test_recompute_all_sponsor_targets_worker(async_session, brand_with_offer):
    brand, _ = brand_with_offer
    result = recompute_all_sponsor_targets()
    assert result["brands"] == 1
    assert result["rows"] == 2 # Two sponsor profiles created in fixture
    assert not result["errors"]

    targets = (await async_session.execute(select(SponsorTarget).where(SponsorTarget.brand_id == brand.id))).scalars().all()
    assert len(targets) == 2
    assert targets[0].brand_id == brand.id
    assert targets[0].target_company_name is not None
    assert targets[0].industry is not None
    assert targets[0].fit_score > 0
    assert targets[0].estimated_deal_value > 0
    assert targets[0].confidence > 0
    assert targets[0].explanation is not None


@pytest.mark.asyncio
async def test_recompute_all_sponsor_outreach_sequences_worker(async_session, brand_with_offer):
    brand, _ = brand_with_offer
    # Need to create sponsor targets first for the sequences to be generated
    result_targets = recompute_all_sponsor_targets()
    assert result_targets["brands"] == 1
    assert result_targets["rows"] == 2 # Two sponsor profiles created in fixture
    assert not result_targets["errors"]

    result = recompute_all_sponsor_outreach_sequences()
    assert result["brands"] == 1
    assert result["rows"] == 2 # Two sponsor targets, so two sequences
    assert not result["errors"]

    sequences = (await async_session.execute(select(SponsorOutreachSequence).join(SponsorTarget).where(SponsorTarget.brand_id == brand.id))).scalars().all()
    assert len(sequences) == 2
    for seq in sequences:
        assert seq.sponsor_target_id is not None
        assert seq.sequence_name is not None
        assert len(seq.steps) > 0
        assert seq.estimated_response_rate > 0
        assert seq.expected_value > 0 # New field
        assert seq.confidence > 0
        assert seq.explanation is not None # New field


@pytest.mark.asyncio
async def test_recompute_all_profit_guardrail_reports_worker(async_session, brand_with_offer):
    brand, _ = brand_with_offer
    result = recompute_all_profit_guardrail_reports()
    assert result["brands"] == 1
    assert result["rows"] >= 1
    assert not result["errors"]

    reports = (await async_session.execute(select(ProfitGuardrailReport).where(ProfitGuardrailReport.brand_id == brand.id))).scalars().all()
    assert len(reports) >= 1
    for r in reports:
        assert r.brand_id == brand.id
        assert r.metric_name is not None
        assert r.status in ("ok", "warning", "violation")
        assert 0 <= r.confidence <= 1
