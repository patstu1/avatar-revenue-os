"""Digital Twin / Simulation API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.digital_twin import DTRunOut, DTScenarioOut, DTRecommendationOut, RecomputeSummaryOut
from apps.api.services import digital_twin_service as svc
from packages.db.models.core import Brand

router = APIRouter()

async def _rb(bid, cu, db):
    b = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not b or b.organization_id != cu.organization_id: raise HTTPException(status_code=404, detail="Brand not found")

@router.get("/{brand_id}/simulations", response_model=list[DTRunOut])
async def runs(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_runs(db, brand_id)

@router.post("/{brand_id}/simulations/run", response_model=RecomputeSummaryOut)
async def run_sim(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db); r = await svc.run_simulation(db, brand_id); await db.commit(); return RecomputeSummaryOut(**r)

@router.get("/{brand_id}/simulations/scenarios", response_model=list[DTScenarioOut])
async def scenarios(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_scenarios(db, brand_id)

@router.get("/{brand_id}/simulations/recommendations", response_model=list[DTRecommendationOut])
async def recommendations(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_recommendations(db, brand_id)
