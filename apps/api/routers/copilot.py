"""Operator Copilot — chat sessions, grounded messages, operator snapshots."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.copilot import (
    CopilotMessageCreate,
    CopilotMessageOut,
    CopilotPostMessagesResponse,
    CopilotSessionCreate,
    CopilotSessionOut,
)
from apps.api.services import copilot_service as svc
from packages.db.models.core import Brand

router = APIRouter()
router_root = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/copilot/sessions", response_model=list[CopilotSessionOut])
async def list_copilot_sessions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        rows = await svc.list_sessions(db, brand_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    return rows


@router.post("/{brand_id}/copilot/sessions", response_model=CopilotSessionOut)
async def create_copilot_session(
    brand_id: uuid.UUID,
    body: CopilotSessionCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    await _require_brand(brand_id, current_user, db)
    try:
        sess = await svc.create_session(db, brand_id, current_user.id, body.title)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    return sess


@router_root.get("/copilot/sessions/{session_id}/messages", response_model=list[CopilotMessageOut])
async def list_copilot_messages(session_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        msgs = await svc.list_messages(db, session_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    if msgs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return msgs


@router_root.post("/copilot/sessions/{session_id}/messages", response_model=CopilotPostMessagesResponse)
async def post_copilot_message(
    session_id: uuid.UUID,
    body: CopilotMessageCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    try:
        pair = await svc.post_message(db, session_id, current_user, body.content, body.quick_prompt_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return CopilotPostMessagesResponse(messages=[CopilotMessageOut.model_validate(m) for m in pair])


@router.get("/{brand_id}/copilot/quick-status")
async def copilot_quick_status(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.get_quick_status_bundle(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/{brand_id}/copilot/operator-actions")
async def copilot_operator_actions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.get_operator_actions_bundle(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/{brand_id}/copilot/missing-items")
async def copilot_missing_items(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.get_missing_items_bundle(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/{brand_id}/copilot/providers")
async def copilot_providers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.get_providers_bundle(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/{brand_id}/copilot/provider-readiness")
async def copilot_provider_readiness(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        return await svc.get_provider_readiness_bundle(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/{brand_id}/copilot/autonomous-readiness")
async def copilot_autonomous_readiness(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        from packages.scoring.autonomous_readiness_engine import evaluate_autonomous_readiness

        return evaluate_autonomous_readiness()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/{brand_id}/copilot/activation-checklist")
async def copilot_activation_checklist(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    try:
        from packages.scoring.autonomous_readiness_engine import get_activation_checklist

        return get_activation_checklist()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
