"""Brand Governance Service — evaluate, persist violations, list, approve."""
from __future__ import annotations
import uuid
from typing import Any
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.brand_governance import (
    BrandGovernanceProfile, BrandVoiceRule, BrandKnowledgeBase,
    BrandAudienceProfile, BrandEditorialRule, BrandAssetLibrary,
    BrandGovernanceViolation, BrandGovernanceApproval,
)
from packages.db.models.content import ContentItem
from packages.scoring.brand_governance_engine import evaluate_voice_rules, score_editorial_compliance, check_audience_fit


async def evaluate_content(db: AsyncSession, brand_id: uuid.UUID, content_item_id: uuid.UUID) -> dict[str, Any]:
    ci = (await db.execute(select(ContentItem).where(ContentItem.id == content_item_id))).scalar_one_or_none()
    if not ci:
        return {"status": "not_found"}

    profile = (await db.execute(select(BrandGovernanceProfile).where(BrandGovernanceProfile.brand_id == brand_id, BrandGovernanceProfile.is_active.is_(True)).limit(1))).scalar_one_or_none()
    voice_rules = list((await db.execute(select(BrandVoiceRule).where(BrandVoiceRule.brand_id == brand_id, BrandVoiceRule.is_active.is_(True)))).scalars().all())
    editorial_rules = list((await db.execute(select(BrandEditorialRule).where(BrandEditorialRule.brand_id == brand_id, BrandEditorialRule.is_active.is_(True)))).scalars().all())

    text = (ci.title or "") + " " + (ci.description or "")
    rule_dicts = [{"id": str(r.id), "rule_type": r.rule_type, "rule_key": r.rule_key, "rule_value": r.rule_value, "severity": r.severity} for r in voice_rules]
    violations = evaluate_voice_rules(text, rule_dicts)

    profile_dict = {"tone_profile": profile.tone_profile if profile else ""}
    ed_dicts = [{"rule_category": r.rule_category, "check_type": r.check_type, "check_value": r.check_value} for r in editorial_rules]
    ct = ci.content_type
    content_dict = {"body_text": ci.description or "", "hook_text": ci.title or "", "content_form": ct.value if hasattr(ct, "value") else str(ct), "cta_type": getattr(ci, "cta_type", None), "monetization_method": ci.monetization_method}
    editorial = score_editorial_compliance(content_dict, ed_dicts, profile_dict)

    await db.execute(delete(BrandGovernanceViolation).where(BrandGovernanceViolation.content_item_id == content_item_id))
    for v in violations:
        rid = None
        if v.get("rule_id"):
            try: rid = uuid.UUID(str(v["rule_id"]))
            except: pass
        db.add(BrandGovernanceViolation(brand_id=brand_id, content_item_id=content_item_id, violation_type=v["violation_type"], rule_id=rid, severity=v["severity"], detail=v["detail"]))

    if editorial["verdict"] == "fail":
        db.add(BrandGovernanceViolation(brand_id=brand_id, content_item_id=content_item_id, violation_type="editorial_fail", severity="hard", detail=f"Editorial score {editorial['total_score']:.2f} below threshold"))

    await db.flush()
    return {"violations": len(violations), "editorial": editorial, "status": "completed"}


async def recompute_governance(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    items = list((await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id, ContentItem.status.in_(("draft", "script_generated", "media_complete", "approved"))).limit(50))).scalars().all())
    count = 0
    for ci in items:
        await evaluate_content(db, brand_id, ci.id)
        count += 1
    return {"rows_processed": count, "status": "completed"}


async def list_profiles(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(BrandGovernanceProfile).where(BrandGovernanceProfile.brand_id == brand_id, BrandGovernanceProfile.is_active.is_(True)))).scalars().all())

async def list_voice_rules(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(BrandVoiceRule).where(BrandVoiceRule.brand_id == brand_id, BrandVoiceRule.is_active.is_(True)))).scalars().all())

async def list_knowledge_bases(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(BrandKnowledgeBase).where(BrandKnowledgeBase.brand_id == brand_id, BrandKnowledgeBase.is_active.is_(True)))).scalars().all())

async def list_audiences(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(BrandAudienceProfile).where(BrandAudienceProfile.brand_id == brand_id, BrandAudienceProfile.is_active.is_(True)))).scalars().all())

async def list_assets(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(BrandAssetLibrary).where(BrandAssetLibrary.brand_id == brand_id, BrandAssetLibrary.is_active.is_(True)))).scalars().all())

async def list_violations(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(BrandGovernanceViolation).where(BrandGovernanceViolation.brand_id == brand_id, BrandGovernanceViolation.is_active.is_(True)).order_by(BrandGovernanceViolation.created_at.desc()).limit(50))).scalars().all())

async def list_approvals(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(select(BrandGovernanceApproval).where(BrandGovernanceApproval.brand_id == brand_id, BrandGovernanceApproval.is_active.is_(True)))).scalars().all())

async def get_governance_for_content(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: return active governance rules for content generation."""
    voice = list((await db.execute(select(BrandVoiceRule).where(BrandVoiceRule.brand_id == brand_id, BrandVoiceRule.is_active.is_(True)))).scalars().all())
    profile = (await db.execute(select(BrandGovernanceProfile).where(BrandGovernanceProfile.brand_id == brand_id, BrandGovernanceProfile.is_active.is_(True)).limit(1))).scalar_one_or_none()
    return {
        "tone_profile": profile.tone_profile if profile else None,
        "governance_level": profile.governance_level if profile else "standard",
        "banned_phrases": [r.rule_key for r in voice if r.rule_type == "banned_phrase"],
        "required_phrases": [r.rule_key for r in voice if r.rule_type == "required_phrase"],
        "disclosure_rules": [{"key": r.rule_key, "value": r.rule_value} for r in voice if r.rule_type == "disclosure"],
    }
