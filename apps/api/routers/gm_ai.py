"""GM AI API — The General Manager interface.

Strategic operating brain that scans, plans, directs, and manages
the entire revenue machine. Includes conversational operator endpoint
with full tool-use execution authority.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import desc, select

from apps.api.deps import CurrentUser, DBSession
from apps.api.services import gm_ai as gm
from apps.api.services import portfolio_gm
from packages.db.models.gm import GMConversation

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class GMChatRequest(BaseModel):
    brand_id: uuid.UUID
    message: str
    conversation_id: uuid.UUID | None = None


class GMChatResponse(BaseModel):
    conversation_id: str
    response: str
    actions_taken: list
    model_config = {"from_attributes": True}


# ── Existing read-only endpoints ─────────────────────────────────────────────

@router.get("/gm/scan")
async def full_scan(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Phase 1: Full system scan — accounts, platforms, revenue, offers, patterns, sponsors, content."""
    return await gm.run_full_scan(db, brand_id)


@router.get("/gm/blueprint")
async def scale_blueprint(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Phase 2: Scale blueprint — platforms, accounts, archetypes, monetization timing, expansion triggers."""
    return await gm.generate_scale_blueprint(db, brand_id)


@router.get("/gm/directive")
async def operating_directive(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Phase 3: Current operating directive — what to do RIGHT NOW, ranked by impact."""
    return await gm.get_gm_directive(db, brand_id)


@router.get("/gm/portfolio")
async def portfolio_overview(current_user: CurrentUser, db: DBSession):
    """Portfolio-level GM — cross-brand strategic view with allocation recommendations."""
    return await portfolio_gm.get_portfolio_overview(db, current_user.organization_id)


@router.get("/gm/portfolio-allocation")
async def portfolio_allocation(current_user: CurrentUser, db: DBSession):
    """Deep portfolio allocator — % effort allocation per brand by marginal return."""
    return await portfolio_gm.compute_portfolio_allocation(db, current_user.organization_id)


@router.get("/gm/status")
async def gm_status(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Quick status check — health, metrics, status line."""
    return await gm.get_gm_status(db, brand_id)


# ── Conversational GM Operator Endpoint ──────────────────────────────────────

@router.post("/gm/chat")
async def gm_chat(
    body: GMChatRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Conversational GM with full execution authority.

    Send a message to the GM. It scans the machine, reasons about strategy,
    and executes real operations via tool-use. Returns the GM's response
    plus a log of every action it took.
    """
    org_id = current_user.organization_id
    brand_id = body.brand_id

    # Load or create conversation
    conversation = None
    conversation_history: list[dict] = []

    if body.conversation_id:
        result = await db.execute(
            select(GMConversation).where(
                GMConversation.id == body.conversation_id,
                GMConversation.organization_id == org_id,
                GMConversation.brand_id == brand_id,
            )
        )
        conversation = result.scalar_one_or_none()

    if conversation and conversation.messages:
        conversation_history = list(conversation.messages)
    elif not conversation:
        conversation = GMConversation(
            organization_id=org_id,
            brand_id=brand_id,
            messages=[],
            actions_log=[],
        )
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)

        # Pre-populate with startup prompt as the first GM message
        # if this is a brand-new conversation with no history
        startup_msg = await gm.get_startup_prompt(db, org_id)
        if startup_msg:
            conversation_history = [{"role": "gm", "content": startup_msg}]

    # Call the conversational GM
    result = await gm.gm_conversation(
        db=db,
        org_id=org_id,
        brand_id=brand_id,
        user_message=body.message,
        conversation_history=conversation_history,
    )

    # Persist conversation history
    updated_messages = list(conversation_history)
    updated_messages.append({"role": "user", "content": body.message})
    updated_messages.append({"role": "gm", "content": result["response"]})
    conversation.messages = updated_messages

    # Persist actions log
    existing_log = list(conversation.actions_log or [])
    for action in result.get("actions_taken", []):
        existing_log.append({
            "tool": action["tool"],
            "input": action["input"],
            "result": action["result"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    conversation.actions_log = existing_log

    await db.flush()

    return {
        "conversation_id": str(conversation.id),
        "response": result["response"],
        "actions_taken": result.get("actions_taken", []),
    }


@router.get("/gm/conversations")
async def list_conversations(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
):
    """List all GM operator conversations for a brand."""
    result = await db.execute(
        select(GMConversation).where(
            GMConversation.organization_id == current_user.organization_id,
            GMConversation.brand_id == brand_id,
            GMConversation.is_active.is_(True),
        ).order_by(desc(GMConversation.updated_at)).limit(20)
    )
    conversations = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "brand_id": str(c.brand_id),
            "message_count": len(c.messages or []),
            "action_count": len(c.actions_log or []),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in conversations
    ]


@router.get("/gm/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Get full conversation history and actions log."""
    result = await db.execute(
        select(GMConversation).where(
            GMConversation.id == conversation_id,
            GMConversation.organization_id == current_user.organization_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "id": str(conversation.id),
        "brand_id": str(conversation.brand_id),
        "messages": conversation.messages or [],
        "actions_log": conversation.actions_log or [],
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }
