"""Brain Architecture Phase C — agent mesh, workflow coordination, context bus, memory binding APIs."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.brain_phase_c import (
    AgentRegistryOut,
    AgentRunV2Out,
    RecomputeSummaryOut,
    SharedContextEventOut,
    WorkflowCoordinationRunOut,
)
from apps.api.services import brain_phase_c_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


@router.get("/{brand_id}/agent-registry", response_model=list[AgentRegistryOut])
async def list_agent_registry(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_agent_registry(db, brand_id)


@router.get("/{brand_id}/agent-runs-v2", response_model=list[AgentRunV2Out])
async def list_agent_runs_v2(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_agent_runs_v2(db, brand_id, limit=limit)


@router.post("/{brand_id}/agent-mesh/recompute", response_model=RecomputeSummaryOut)
async def recompute_agent_mesh(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_agent_mesh(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=(
                f"Agent mesh — {result.get('registry_created', 0)} agents, "
                f"{result.get('agent_runs_created', 0)} runs, "
                f"{result.get('workflows_created', 0)} workflows, "
                f"{result.get('context_events_created', 0)} context events"
            ),
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/workflow-coordination", response_model=list[WorkflowCoordinationRunOut])
async def list_workflow_coordination(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_workflow_coordination(db, brand_id, limit=limit)


@router.get("/{brand_id}/shared-context-events", response_model=list[SharedContextEventOut])
async def list_shared_context_events(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(200, ge=1, le=1000),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_shared_context_events(db, brand_id, limit=limit)
