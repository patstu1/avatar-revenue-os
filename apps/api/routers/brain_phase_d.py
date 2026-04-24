"""Brain Architecture Phase D — meta-monitoring, self-correction, readiness, escalation APIs."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.brain_phase_d import (
    BrainEscalationOut,
    MetaMonitoringReportOut,
    ReadinessBrainReportOut,
    RecomputeSummaryOut,
    SelfCorrectionActionOut,
)
from apps.api.services import brain_phase_d_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/meta-monitoring", response_model=list[MetaMonitoringReportOut])
async def list_meta_monitoring(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(20, ge=1, le=100),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_meta_monitoring(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.post("/{brand_id}/meta-monitoring/recompute", response_model=RecomputeSummaryOut)
async def recompute_meta_monitoring(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_meta_monitoring(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=(
                f"Meta-monitoring — {result.get('corrections_created', 0)} corrections, "
                f"{result.get('escalations_created', 0)} escalations"
            ),
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/self-corrections", response_model=list[SelfCorrectionActionOut])
async def list_self_corrections(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_self_corrections(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/{brand_id}/readiness-brain", response_model=list[ReadinessBrainReportOut])
async def list_readiness_brain(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(10, ge=1, le=50),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_readiness_brain(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.post("/{brand_id}/readiness-brain/recompute", response_model=RecomputeSummaryOut)
async def recompute_readiness_brain(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_readiness_brain(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=f"Readiness brain — score computed, {result.get('escalations_created', 0)} escalations",
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/brain-escalations", response_model=list[BrainEscalationOut])
async def list_brain_escalations(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.list_brain_escalations(db, brand_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
