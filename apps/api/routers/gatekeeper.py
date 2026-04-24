"""AI Gatekeeper API — hard internal control system."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.gatekeeper import (
    AlertOut,
    AuditLedgerOut,
    CompletionReportOut,
    ContradictionReportOut,
    DependencyReportOut,
    ExecutionClosureReportOut,
    ExpansionPermissionOut,
    OperatorCommandReportOut,
    RecomputeSummaryOut,
    TestReportOut,
    TruthReportOut,
)
from apps.api.services import gatekeeper_service as gk
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.get("/{brand_id}/gatekeeper/completion", response_model=list[CompletionReportOut])
async def get_completion(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_completion(db, brand_id)


@router.post("/{brand_id}/gatekeeper/completion/recompute", response_model=RecomputeSummaryOut)
async def recompute_completion(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_completion(db, brand_id)


@router.get("/{brand_id}/gatekeeper/truth", response_model=list[TruthReportOut])
async def get_truth(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_truth(db, brand_id)


@router.post("/{brand_id}/gatekeeper/truth/recompute", response_model=RecomputeSummaryOut)
async def recompute_truth(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_truth(db, brand_id)


@router.get("/{brand_id}/gatekeeper/execution-closure", response_model=list[ExecutionClosureReportOut])
async def get_execution_closure(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_execution_closure(db, brand_id)


@router.post("/{brand_id}/gatekeeper/execution-closure/recompute", response_model=RecomputeSummaryOut)
async def recompute_execution_closure(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_execution_closure(db, brand_id)


@router.get("/{brand_id}/gatekeeper/tests", response_model=list[TestReportOut])
async def get_tests(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_tests(db, brand_id)


@router.post("/{brand_id}/gatekeeper/tests/recompute", response_model=RecomputeSummaryOut)
async def recompute_tests(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_tests(db, brand_id)


@router.get("/{brand_id}/gatekeeper/dependencies", response_model=list[DependencyReportOut])
async def get_dependencies(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_dependencies(db, brand_id)


@router.post("/{brand_id}/gatekeeper/dependencies/recompute", response_model=RecomputeSummaryOut)
async def recompute_dependencies(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_dependencies(db, brand_id)


@router.get("/{brand_id}/gatekeeper/contradictions", response_model=list[ContradictionReportOut])
async def get_contradictions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_contradictions(db, brand_id)


@router.post("/{brand_id}/gatekeeper/contradictions/recompute", response_model=RecomputeSummaryOut)
async def recompute_contradictions(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_contradictions(db, brand_id)


@router.get("/{brand_id}/gatekeeper/operator-commands", response_model=list[OperatorCommandReportOut])
async def get_operator_commands(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_operator_commands(db, brand_id)


@router.post("/{brand_id}/gatekeeper/operator-commands/recompute", response_model=RecomputeSummaryOut)
async def recompute_operator_commands(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_operator_commands(db, brand_id)


@router.get("/{brand_id}/gatekeeper/expansion-permissions", response_model=list[ExpansionPermissionOut])
async def get_expansion_permissions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_expansion_permissions(db, brand_id)


@router.post("/{brand_id}/gatekeeper/expansion-permissions/recompute", response_model=RecomputeSummaryOut)
async def recompute_expansion_permissions(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.recompute_expansion_permissions(db, brand_id)


@router.get("/{brand_id}/gatekeeper/alerts", response_model=list[AlertOut])
async def get_alerts(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_alerts(db, brand_id)


@router.get("/{brand_id}/gatekeeper/audit-ledger", response_model=list[AuditLedgerOut])
async def get_audit_ledger(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gk.list_audit_ledger(db, brand_id)
