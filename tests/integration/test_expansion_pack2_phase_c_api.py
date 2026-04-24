import pytest
from httpx import AsyncClient
from sqlalchemy import select

from packages.db.enums import MonetizationMethod
from packages.db.models.core import Brand, Organization
from packages.db.models.expansion_pack2_phase_c import (
    ProfitGuardrailReport,
    ReferralProgramRecommendation,
)
from packages.db.models.offers import AudienceSegment, Offer, SponsorProfile
from tests.conftest import create_access_token_for_user, make_operator_user


@pytest.fixture
async def brand_with_offer(async_session):
    organization = Organization(name="Test Org", slug="ep2c-test")
    async_session.add(organization)
    await async_session.flush()

    brand = Brand(name="Test Brand", slug="ep2c-brand", organization_id=organization.id)
    async_session.add(brand)
    await async_session.flush()

    offer = Offer(
        brand_id=brand.id,
        name="Test Offer",
        description="A test offer",
        monetization_method=MonetizationMethod.AFFILIATE,
        payout_amount=100.0,
        is_active=True,
    )
    async_session.add(offer)

    high_value_segment = AudienceSegment(
        brand_id=brand.id,
        name="High-Value Loyal Customers",
        description="Customers with high loyalty and purchase value",
        estimated_size=1000,
        revenue_contribution=50000.0,
        conversion_rate=0.08,
        avg_ltv=500.0,
    )
    async_session.add(high_value_segment)

    new_customer_segment = AudienceSegment(
        brand_id=brand.id,
        name="New Engaged Customers",
        description="Recently acquired and engaged customers",
        estimated_size=2000,
        revenue_contribution=20000.0,
        conversion_rate=0.03,
        avg_ltv=100.0,
    )
    async_session.add(new_customer_segment)

    general_segment = AudienceSegment(
        brand_id=brand.id,
        name="General Audience",
        description="Broad audience segment",
        estimated_size=10000,
        revenue_contribution=75000.0,
        conversion_rate=0.02,
        avg_ltv=75.0,
    )
    async_session.add(general_segment)

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


@pytest.fixture
async def operator_user(async_session, brand_with_offer):
    brand, _ = brand_with_offer
    user = make_operator_user(brand.organization_id)
    async_session.add(user)
    await async_session.commit()
    return user


@pytest.mark.asyncio
async def test_recompute_referral_program_recommendations(
    client: AsyncClient, operator_user, brand_with_offer, async_session
):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    response = await client.post(
        f"/api/v1/brands/{brand.id}/referral-programs/recompute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["referral_recommendations_count"] == 1

    recommendations = (
        (
            await async_session.execute(
                select(ReferralProgramRecommendation).where(ReferralProgramRecommendation.brand_id == brand.id)
            )
        )
        .scalars()
        .all()
    )
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
async def test_list_referral_program_recommendations(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/referral-programs/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/referral-programs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["brand_id"] == str(brand.id)
    assert data[0]["customer_segment"] is not None
    assert data[0]["recommendation_type"] is not None
    assert data[0]["referral_bonus"] > 0
    assert data[0]["referred_bonus"] > 0
    assert data[0]["estimated_conversion_rate"] > 0
    assert data[0]["estimated_revenue_impact"] > 0
    assert data[0]["confidence"] > 0


@pytest.mark.asyncio
async def test_recompute_competitive_gap_reports(client: AsyncClient, operator_user, brand_with_offer):
    brand, offer = brand_with_offer
    token = create_access_token_for_user(operator_user)
    response = await client.post(
        f"/api/v1/brands/{brand.id}/competitive-gaps/recompute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["competitive_gap_reports_count"] == 1


@pytest.mark.asyncio
async def test_list_competitive_gap_reports(client: AsyncClient, operator_user, brand_with_offer):
    brand, offer = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/competitive-gaps/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/competitive-gaps", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["brand_id"] == str(brand.id)
    assert data[0]["gap_type"] in (
        "pricing_disadvantage",
        "feature_disadvantage",
        "customer_satisfaction_gap",
        "no_significant_gap",
    )
    assert data[0]["severity"] in ("low", "medium", "high", "critical")
    assert data[0]["estimated_impact"] >= 0
    assert data[0]["confidence"] > 0
    assert data[0]["gap_description"] is not None


@pytest.mark.asyncio
async def test_list_sponsor_targets(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/sponsor-targets/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/sponsor-targets", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["brand_id"] == str(brand.id)
    assert data[0]["target_company_name"] is not None
    assert data[0]["industry"] is not None
    assert data[0]["fit_score"] > 0
    assert data[0]["estimated_deal_value"] > 0
    assert data[0]["confidence"] > 0
    assert data[0]["explanation"] is not None


@pytest.mark.asyncio
async def test_recompute_sponsor_outreach_sequences(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/sponsor-targets/recompute", headers=headers)

    response = await client.post(f"/api/v1/brands/{brand.id}/sponsor-outreach/recompute", headers=headers)
    assert response.status_code == 200
    assert response.json()["sponsor_outreach_sequences_count"] == 2


@pytest.mark.asyncio
async def test_list_sponsor_outreach_sequences(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/sponsor-targets/recompute", headers=headers)
    await client.post(f"/api/v1/brands/{brand.id}/sponsor-outreach/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/sponsor-outreach", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["sponsor_target_id"] is not None
    assert data[0]["sequence_name"] is not None
    assert len(data[0]["steps"]) > 0
    assert data[0]["estimated_response_rate"] > 0
    assert data[0]["expected_value"] > 0
    assert data[0]["confidence"] > 0
    assert data[0]["explanation"] is not None


@pytest.mark.asyncio
async def test_profitable_buyer_segment_gets_referral_recommendation(
    client: AsyncClient, operator_user, brand_with_offer
):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(f"/api/v1/brands/{brand.id}/referral-programs/recompute", headers=headers)
    assert response.status_code == 200
    assert response.json()["referral_recommendations_count"] == 1

    response = await client.get(f"/api/v1/brands/{brand.id}/referral-programs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["customer_segment"] is not None
    assert data[0]["recommendation_type"] is not None


@pytest.mark.asyncio
async def test_sponsor_target_list_generates_outreach_sequence(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/sponsor-targets/recompute", headers=headers)
    response = await client.post(f"/api/v1/brands/{brand.id}/sponsor-outreach/recompute", headers=headers)
    assert response.status_code == 200
    assert response.json()["sponsor_outreach_sequences_count"] == 2

    response = await client.get(f"/api/v1/brands/{brand.id}/sponsor-outreach", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert len(data[0]["steps"]) > 0


@pytest.mark.asyncio
async def test_recompute_profit_guardrail_reports(client: AsyncClient, operator_user, brand_with_offer, async_session):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    response = await client.post(
        f"/api/v1/brands/{brand.id}/profit-guardrails/recompute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["profit_guardrail_reports_count"] >= 1

    reports = (
        (await async_session.execute(select(ProfitGuardrailReport).where(ProfitGuardrailReport.brand_id == brand.id)))
        .scalars()
        .all()
    )
    assert len(reports) >= 1
    for r in reports:
        assert r.brand_id == brand.id
        assert r.metric_name is not None
        assert r.status in ("ok", "warning", "violation")
        assert 0 <= r.confidence <= 1


@pytest.mark.asyncio
async def test_list_profit_guardrail_reports(client: AsyncClient, operator_user, brand_with_offer):
    brand, _ = brand_with_offer
    token = create_access_token_for_user(operator_user)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/brands/{brand.id}/profit-guardrails/recompute", headers=headers)

    response = await client.get(f"/api/v1/brands/{brand.id}/profit-guardrails", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    for r in data:
        assert r["brand_id"] == str(brand.id)
        assert r["metric_name"] is not None
        assert r["status"] in ("ok", "warning", "violation")
        assert 0 <= r["confidence"] <= 1
