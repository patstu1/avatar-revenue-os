"""DB-backed integration tests for Enterprise Affiliate."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.affiliate_enterprise_service import (
    list_banned,
    list_governance_rules,
    list_partners,
    list_risk_flags,
    recompute_governance,
    recompute_partner_scores,
)
from packages.db.models.affiliate_enterprise import (
    AffiliateBannedEntity,
    AffiliateGovernanceRule,
    AffiliateRiskFlag,
    OwnedAffiliatePartner,
    OwnedPartnerConversion,
)
from packages.db.models.affiliate_intel import AffiliateMerchant, AffiliateOffer
from packages.db.models.core import Organization


@pytest_asyncio.fixture
async def org_with_affiliate(db_session: AsyncSession):
    slug = f"afe-{uuid.uuid4().hex[:6]}"
    org = Organization(name="AFE Org", slug=f"org-{slug}")
    db_session.add(org); await db_session.flush()

    from packages.db.models.core import Brand
    brand = Brand(organization_id=org.id, name="AFE Brand", slug=slug, niche="tech")
    db_session.add(brand); await db_session.flush()

    merchant = AffiliateMerchant(brand_id=brand.id, merchant_name="Test Merchant", trust_score=0.8)
    db_session.add(merchant); await db_session.flush()

    good = AffiliateOffer(brand_id=brand.id, merchant_id=merchant.id, product_name="Good Offer", epc=3.0, conversion_rate=0.05, commission_rate=20, trust_score=0.8, affiliate_url="https://aff.com/good")
    risky = AffiliateOffer(brand_id=brand.id, merchant_id=merchant.id, product_name="Risky Offer", epc=0, conversion_rate=0, commission_rate=5, trust_score=0.2, refund_rate=0.25)
    db_session.add_all([good, risky]); await db_session.flush()

    db_session.add(AffiliateGovernanceRule(organization_id=org.id, rule_type="max_commission_rate", rule_key="global_max", rule_value={"max": 50}))
    db_session.add(AffiliateBannedEntity(organization_id=org.id, entity_type="merchant", entity_name="ScamCo", reason="Known fraud"))

    partner = OwnedAffiliatePartner(organization_id=org.id, partner_name="Good Partner", partner_status="active", total_conversions=50, conversion_quality=0.7, fraud_risk=0.1, total_revenue_generated=2000)
    db_session.add(partner); await db_session.flush()
    for i in range(5):
        db_session.add(OwnedPartnerConversion(partner_id=partner.id, conversion_value=40, commission_paid=8, quality_score=0.8))
    await db_session.flush()

    return org, brand


@pytest.mark.asyncio
async def test_recompute_governance(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    result = await recompute_governance(db_session, org.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["risk_flags"] >= 1


@pytest.mark.asyncio
async def test_risk_flags_persisted(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    await recompute_governance(db_session, org.id); await db_session.commit()
    flags = (await db_session.execute(select(AffiliateRiskFlag).where(AffiliateRiskFlag.organization_id == org.id))).scalars().all()
    assert len(flags) >= 1
    types = {f.risk_type for f in flags}
    assert "low_trust" in types or "high_refund" in types or "no_epc_data" in types


@pytest.mark.asyncio
async def test_recompute_partner_scores(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    result = await recompute_partner_scores(db_session, org.id)
    await db_session.commit()
    assert result["status"] == "completed"
    assert result["rows_processed"] == 1


@pytest.mark.asyncio
async def test_partner_score_updated(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    await recompute_partner_scores(db_session, org.id); await db_session.commit()
    partners = (await db_session.execute(select(OwnedAffiliatePartner).where(OwnedAffiliatePartner.organization_id == org.id))).scalars().all()
    assert partners[0].partner_score > 0


@pytest.mark.asyncio
async def test_list_governance_rules(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    rules = await list_governance_rules(db_session, org.id)
    assert len(rules) == 1


@pytest.mark.asyncio
async def test_list_banned(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    banned = await list_banned(db_session, org.id)
    assert len(banned) == 1
    assert banned[0].entity_name == "ScamCo"


@pytest.mark.asyncio
async def test_list_risk_flags(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    await recompute_governance(db_session, org.id); await db_session.commit()
    flags = await list_risk_flags(db_session, org.id)
    assert len(flags) >= 1


@pytest.mark.asyncio
async def test_list_partners(db_session, org_with_affiliate):
    org, _ = org_with_affiliate
    partners = await list_partners(db_session, org.id)
    assert len(partners) == 1
