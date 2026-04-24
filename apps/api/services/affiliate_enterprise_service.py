"""Enterprise Affiliate Service — governance, risk, owned program."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.affiliate_enterprise import (
    AffiliateApproval,
    AffiliateAuditEvent,
    AffiliateBannedEntity,
    AffiliateGovernanceRule,
    AffiliateRiskFlag,
    OwnedAffiliatePartner,
    OwnedPartnerConversion,
)
from packages.db.models.affiliate_intel import AffiliateOffer
from packages.scoring.affiliate_enterprise_engine import (
    detect_partner_fraud,
    flag_risk,
    score_partner,
)


async def recompute_governance(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(AffiliateRiskFlag).where(AffiliateRiskFlag.organization_id == org_id))

    offers = list((await db.execute(select(AffiliateOffer).where(AffiliateOffer.brand_id.in_(select(AffiliateOffer.brand_id).where(AffiliateOffer.is_active.is_(True)))))).scalars().all())
    rules = list((await db.execute(select(AffiliateGovernanceRule).where(AffiliateGovernanceRule.organization_id == org_id, AffiliateGovernanceRule.is_active.is_(True)))).scalars().all())
    banned = list((await db.execute(select(AffiliateBannedEntity).where(AffiliateBannedEntity.organization_id == org_id, AffiliateBannedEntity.is_active.is_(True)))).scalars().all())

    [{"rule_type": r.rule_type, "rule_key": r.rule_key, "rule_value": r.rule_value, "severity": r.severity} for r in rules]
    [{"entity_type": b.entity_type, "entity_name": b.entity_name, "reason": b.reason} for b in banned]

    total_flags = 0
    for o in offers:
        offer_dict = {"merchant_name": "", "product_category": o.product_category, "commission_rate": float(o.commission_rate), "trust_score": float(o.trust_score), "refund_rate": float(o.refund_rate), "epc": float(o.epc), "approved": True}
        flags = flag_risk(offer_dict)
        for f in flags:
            db.add(AffiliateRiskFlag(organization_id=org_id, offer_id=o.id, risk_type=f["risk_type"], risk_score=f["risk_score"], detail=f["detail"]))
            total_flags += 1

    await db.flush()
    return {"rows_processed": len(offers), "risk_flags": total_flags, "status": "completed"}


async def recompute_partner_scores(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    partners = list((await db.execute(select(OwnedAffiliatePartner).where(OwnedAffiliatePartner.organization_id == org_id, OwnedAffiliatePartner.is_active.is_(True)))).scalars().all())
    for p in partners:
        convs = list((await db.execute(select(OwnedPartnerConversion).where(OwnedPartnerConversion.partner_id == p.id))).scalars().all())
        pdict = {"total_conversions": p.total_conversions, "conversion_quality": float(p.conversion_quality), "fraud_risk": float(p.fraud_risk), "total_revenue_generated": float(p.total_revenue_generated)}
        scored = score_partner(pdict)
        p.partner_score = scored["partner_score"]

        conv_dicts = [{"quality_score": float(c.quality_score), "fraud_flag": c.fraud_flag} for c in convs]
        fraud_flags = detect_partner_fraud(conv_dicts)
        if fraud_flags:
            p.fraud_risk = min(1.0, float(p.fraud_risk) + 0.2)

    await db.flush()
    return {"rows_processed": len(partners), "status": "completed"}


async def list_governance_rules(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateGovernanceRule).where(AffiliateGovernanceRule.organization_id == org_id, AffiliateGovernanceRule.is_active.is_(True)))).scalars().all())

async def list_banned(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateBannedEntity).where(AffiliateBannedEntity.organization_id == org_id, AffiliateBannedEntity.is_active.is_(True)))).scalars().all())

async def list_approvals(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateApproval).where(AffiliateApproval.organization_id == org_id, AffiliateApproval.is_active.is_(True)))).scalars().all())

async def list_risk_flags(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateRiskFlag).where(AffiliateRiskFlag.organization_id == org_id, AffiliateRiskFlag.is_active.is_(True)))).scalars().all())

async def list_partners(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(OwnedAffiliatePartner).where(OwnedAffiliatePartner.organization_id == org_id, OwnedAffiliatePartner.is_active.is_(True)).order_by(OwnedAffiliatePartner.partner_score.desc()))).scalars().all())

async def list_audit(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(AffiliateAuditEvent).where(AffiliateAuditEvent.organization_id == org_id).order_by(AffiliateAuditEvent.created_at.desc()).limit(50))).scalars().all())
