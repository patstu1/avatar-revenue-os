"""Brand Governance API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.brand_governance import BGProfileOut, BGVoiceRuleOut, BGViolationOut, BGApprovalOut, BGKnowledgeBaseOut, BGAudienceOut, BGAssetOut, RecomputeSummaryOut
from apps.api.services import brand_governance_service as svc
from packages.db.models.core import Brand

router = APIRouter()

async def _rb(bid, cu, db):
    b = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not b or b.organization_id != cu.organization_id: raise HTTPException(status_code=403, detail="Brand not accessible")

@router.get("/{brand_id}/governance-profiles", response_model=list[BGProfileOut])
async def profiles(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_profiles(db, brand_id)

@router.get("/{brand_id}/governance-voice-rules", response_model=list[BGVoiceRuleOut])
async def voice_rules(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_voice_rules(db, brand_id)

@router.get("/{brand_id}/governance-knowledge", response_model=list[BGKnowledgeBaseOut])
async def knowledge(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_knowledge_bases(db, brand_id)

@router.get("/{brand_id}/governance-audiences", response_model=list[BGAudienceOut])
async def audiences(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_audiences(db, brand_id)

@router.get("/{brand_id}/governance-assets", response_model=list[BGAssetOut])
async def assets(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_assets(db, brand_id)

@router.get("/{brand_id}/governance-violations", response_model=list[BGViolationOut])
async def violations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_violations(db, brand_id)

@router.get("/{brand_id}/governance-approvals", response_model=list[BGApprovalOut])
async def approvals(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_approvals(db, brand_id)

@router.post("/{brand_id}/governance/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db); r = await svc.recompute_governance(db, brand_id); await db.commit(); return RecomputeSummaryOut(**r)

@router.post("/{brand_id}/governance/{content_item_id}/evaluate")
async def evaluate(brand_id: uuid.UUID, content_item_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _rb(brand_id, current_user, db); r = await svc.evaluate_content(db, brand_id, content_item_id); await db.commit(); return r
