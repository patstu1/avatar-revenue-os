"""Orchestration Hub API — unified worker/job/provider surface for the operator.

Makes the orchestration layer observable: job throughput, provider health,
failure patterns, stuck jobs, and actionable recovery.
"""
import uuid

from fastapi import APIRouter, Query

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import orchestration_bridge as orch

router = APIRouter()


@router.get("/orchestration/state")
async def get_orchestration_state(
    current_user: CurrentUser,
    db: DBSession,
):
    """Full orchestration state: jobs, queues, throughput, failures.

    Returns running jobs, recent failures, throughput metrics,
    and queue distribution for the last 24 hours.
    """
    return await orch.get_orchestration_state(db, current_user.organization_id)


@router.get("/orchestration/providers")
async def get_provider_health(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(None),
):
    """Provider health: which providers are working, degraded, or blocked."""
    return await orch.get_provider_health(db, brand_id)


@router.get("/orchestration/provider-check")
async def check_provider_ready(
    current_user: CurrentUser,
    db: DBSession,
    provider_key: str = Query(...),
    brand_id: uuid.UUID = Query(None),
):
    """Check if a specific provider is ready for use before routing."""
    return await orch.check_provider_ready(db, provider_key, brand_id)


@router.post("/orchestration/surface-actions")
async def surface_orchestration_actions(
    current_user: OperatorUser,
    db: DBSession,
):
    """Scan for stuck jobs, exhausted retries, and provider blockers.

    Creates operator actions for issues needing attention.
    """
    actions = await orch.surface_orchestration_actions(db, current_user.organization_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}
