"""GM Strategic Chat — Portfolio-level conversational AI endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select

from apps.api.deps import CurrentUser, DBSession
from apps.api.services import gm_startup
from packages.db.models.gm import GMBlueprint, GMMessage, GMSession

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GMSessionCreate(BaseModel):
    title: str = "GM Strategy Session"


class GMMessageCreate(BaseModel):
    content: str


class GMSessionOut(BaseModel):
    id: str
    title: str
    status: str
    machine_phase: str | None = None
    message_count: int
    created_at: str

    model_config = {"from_attributes": True}


class GMMessageOut(BaseModel):
    id: str
    role: str
    content: str
    message_type: str
    blueprint_data: dict | None = None
    created_at: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Machine State & Startup
# ---------------------------------------------------------------------------

@router.get("/gm/machine-state")
async def get_machine_state(current_user: CurrentUser, db: DBSession):
    """Scan full machine state — the GM's eyes."""
    return await gm_startup.get_machine_state(db, current_user.organization_id)


@router.get("/gm/startup-prompt")
async def startup_prompt(current_user: CurrentUser, db: DBSession):
    """State-aware GM opening — returns phase, checklist, and opening message."""
    return await gm_startup.get_startup_prompt(db, current_user.organization_id)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post("/gm/sessions")
async def create_session(
    body: GMSessionCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Create a new GM session and auto-generate the initial blueprint."""
    # Get machine state
    state = await gm_startup.get_machine_state(db, current_user.organization_id)

    # Create session
    session = GMSession(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        title=body.title,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Generate initial blueprint
    result = await gm_startup.generate_launch_blueprint(
        db, current_user.organization_id, state,
    )

    # Save GM's opening message
    gm_message = GMMessage(
        session_id=session.id,
        role="gm",
        content=result["content"],
        message_type="blueprint_presentation",
        blueprint_data=result.get("blueprint"),
        machine_state_snapshot=state,
        generation_model=result.get("model", "unknown"),
    )
    db.add(gm_message)

    # Save blueprint if generated
    if result.get("blueprint"):
        bp_data = result["blueprint"]
        blueprint = GMBlueprint(
            organization_id=current_user.organization_id,
            session_id=session.id,
            version=1,
            status="proposed",
            account_blueprint=bp_data.get("account_blueprint"),
            niche_blueprint=bp_data.get("niche_blueprint"),
            identity_blueprint=bp_data.get("identity_blueprint"),
            platform_blueprint=bp_data.get("platform_blueprint"),
            monetization_blueprint=bp_data.get("monetization_blueprint"),
            scaling_blueprint=bp_data.get("scaling_blueprint"),
            operator_inputs_needed=bp_data.get("operator_inputs_needed"),
            machine_assessment=bp_data.get("machine_assessment"),
        )
        db.add(blueprint)
        await db.flush()
        session.active_blueprint_id = blueprint.id

    session.message_count = 1
    session.last_message_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "session": {
            "id": str(session.id),
            "title": session.title,
        },
        "initial_message": {
            "id": str(gm_message.id),
            "role": "gm",
            "content": result["content"],
            "message_type": "blueprint_presentation",
            "blueprint_data": result.get("blueprint"),
        },
        "machine_state": state,
    }


@router.get("/gm/sessions")
async def list_sessions(current_user: CurrentUser, db: DBSession):
    """List all GM sessions for the organization."""
    result = await db.execute(
        select(GMSession).where(
            GMSession.organization_id == current_user.organization_id,
            GMSession.is_active == True,  # noqa: E712
        ).order_by(desc(GMSession.created_at)).limit(20)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "title": s.title,
            "status": s.status,
            "machine_phase": s.machine_phase,
            "message_count": s.message_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@router.get("/gm/sessions/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Get all messages in a GM session."""
    session = await _get_session(db, session_id, current_user.organization_id)
    result = await db.execute(
        select(GMMessage).where(
            GMMessage.session_id == session.id,
            GMMessage.is_active == True,  # noqa: E712
        ).order_by(GMMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "message_type": m.message_type,
            "blueprint_data": m.blueprint_data,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.post("/gm/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: GMMessageCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Send a message to the GM and get a response."""
    session = await _get_session(db, session_id, current_user.organization_id)

    # Save user message
    user_msg = GMMessage(
        session_id=session.id,
        role="user",
        content=body.content,
        message_type="conversation",
    )
    db.add(user_msg)
    await db.flush()

    # Get machine state + conversation history
    state = await gm_startup.get_machine_state(db, current_user.organization_id)

    history_result = await db.execute(
        select(GMMessage).where(
            GMMessage.session_id == session.id,
            GMMessage.is_active == True,  # noqa: E712
        ).order_by(GMMessage.created_at)
    )
    history = [
        {"role": m.role if m.role != "gm" else "assistant", "content": m.content}
        for m in history_result.scalars().all()
    ]

    # Get current blueprint content if exists
    blueprint_content = None
    if session.active_blueprint_id:
        bp_result = await db.execute(
            select(GMBlueprint).where(GMBlueprint.id == session.active_blueprint_id)
        )
        bp = bp_result.scalar_one_or_none()
        if bp:
            # Check if this is a revision request
            revision_keywords = ["change", "revise", "update", "adjust", "swap", "replace", "drop", "add more", "instead"]
            is_revision = any(kw in body.content.lower() for kw in revision_keywords)

            if is_revision:
                result = await gm_startup.revise_blueprint(
                    db, current_user.organization_id, state,
                    blueprint_content or "", body.content, history,
                )
                message_type = "blueprint_revision"

                # Update blueprint if revision succeeded
                if result.get("blueprint"):
                    bp_data = result["blueprint"]
                    new_bp = GMBlueprint(
                        organization_id=current_user.organization_id,
                        session_id=session.id,
                        version=(bp.version or 1) + 1,
                        status="proposed",
                        account_blueprint=bp_data.get("account_blueprint", bp.account_blueprint),
                        niche_blueprint=bp_data.get("niche_blueprint", bp.niche_blueprint),
                        identity_blueprint=bp_data.get("identity_blueprint", bp.identity_blueprint),
                        platform_blueprint=bp_data.get("platform_blueprint", bp.platform_blueprint),
                        monetization_blueprint=bp_data.get("monetization_blueprint", bp.monetization_blueprint),
                        scaling_blueprint=bp_data.get("scaling_blueprint", bp.scaling_blueprint),
                        operator_inputs_needed=bp_data.get("operator_inputs_needed", bp.operator_inputs_needed),
                        machine_assessment=bp_data.get("machine_assessment", bp.machine_assessment),
                    )
                    db.add(new_bp)
                    await db.flush()
                    bp.status = "superseded"
                    session.active_blueprint_id = new_bp.id
            else:
                result = await gm_startup.gm_conversation(
                    db, current_user.organization_id, state,
                    blueprint_content, history, body.content,
                )
                message_type = "conversation"
        else:
            result = await gm_startup.gm_conversation(
                db, current_user.organization_id, state,
                None, history, body.content,
            )
            message_type = "conversation"
    else:
        result = await gm_startup.gm_conversation(
            db, current_user.organization_id, state,
            None, history, body.content,
        )
        message_type = "conversation"

    # Save GM response
    gm_msg = GMMessage(
        session_id=session.id,
        role="gm",
        content=result["content"],
        message_type=message_type,
        blueprint_data=result.get("blueprint"),
        machine_state_snapshot=state,
        generation_model=result.get("model"),
    )
    db.add(gm_msg)

    session.message_count = (session.message_count or 0) + 2
    session.last_message_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "user_message": {
            "id": str(user_msg.id),
            "role": "user",
            "content": body.content,
            "message_type": "conversation",
        },
        "gm_message": {
            "id": str(gm_msg.id),
            "role": "gm",
            "content": result["content"],
            "message_type": message_type,
            "blueprint_data": result.get("blueprint"),
        },
    }


# ---------------------------------------------------------------------------
# Blueprint Operations
# ---------------------------------------------------------------------------

@router.get("/gm/blueprint")
async def get_active_blueprint(current_user: CurrentUser, db: DBSession):
    """Get the most recent active blueprint."""
    result = await db.execute(
        select(GMBlueprint).where(
            GMBlueprint.organization_id == current_user.organization_id,
            GMBlueprint.status.in_(["proposed", "approved", "executing"]),
            GMBlueprint.is_active == True,  # noqa: E712
        ).order_by(desc(GMBlueprint.created_at)).limit(1)
    )
    bp = result.scalar_one_or_none()
    if not bp:
        raise HTTPException(status_code=404, detail="No active blueprint")

    return {
        "id": str(bp.id),
        "version": bp.version,
        "status": bp.status,
        "account_blueprint": bp.account_blueprint,
        "niche_blueprint": bp.niche_blueprint,
        "identity_blueprint": bp.identity_blueprint,
        "platform_blueprint": bp.platform_blueprint,
        "monetization_blueprint": bp.monetization_blueprint,
        "scaling_blueprint": bp.scaling_blueprint,
        "operator_inputs_needed": bp.operator_inputs_needed,
        "machine_assessment": bp.machine_assessment,
        "execution_progress": bp.execution_progress,
        "approved_at": bp.approved_at.isoformat() if bp.approved_at else None,
        "created_at": bp.created_at.isoformat() if bp.created_at else None,
    }


@router.post("/gm/blueprint/approve")
async def approve_blueprint(current_user: CurrentUser, db: DBSession):
    """Approve the current proposed blueprint for execution."""
    result = await db.execute(
        select(GMBlueprint).where(
            GMBlueprint.organization_id == current_user.organization_id,
            GMBlueprint.status == "proposed",
            GMBlueprint.is_active == True,  # noqa: E712
        ).order_by(desc(GMBlueprint.created_at)).limit(1)
    )
    bp = result.scalar_one_or_none()
    if not bp:
        raise HTTPException(status_code=404, detail="No proposed blueprint to approve")

    bp.status = "approved"
    bp.approved_at = datetime.now(timezone.utc)
    bp.execution_progress = {}
    await db.flush()

    return {"id": str(bp.id), "status": "approved", "approved_at": bp.approved_at.isoformat()}


@router.post("/gm/blueprint/execute/{step_key}")
async def execute_step(
    step_key: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """Execute a specific step from the approved blueprint."""
    result = await db.execute(
        select(GMBlueprint).where(
            GMBlueprint.organization_id == current_user.organization_id,
            GMBlueprint.status.in_(["approved", "executing"]),
            GMBlueprint.is_active == True,  # noqa: E712
        ).order_by(desc(GMBlueprint.created_at)).limit(1)
    )
    bp = result.scalar_one_or_none()
    if not bp:
        raise HTTPException(status_code=404, detail="No approved blueprint to execute")

    bp.status = "executing"
    exec_result = await gm_startup.execute_blueprint_step(
        db, current_user.organization_id, bp, step_key,
    )

    progress = bp.execution_progress or {}
    progress[step_key] = {
        "status": "completed" if exec_result["success"] else "failed",
        "result": exec_result,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    bp.execution_progress = progress

    # Check if all steps completed
    expected_steps = ["create_brands", "create_accounts", "create_offers"]
    all_done = all(
        progress.get(s, {}).get("status") == "completed"
        for s in expected_steps
    )
    if all_done:
        bp.status = "completed"
        bp.completed_at = datetime.now(timezone.utc)

    await db.flush()
    return exec_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_session(
    db: DBSession, session_id: uuid.UUID, org_id: uuid.UUID
) -> GMSession:
    result = await db.execute(
        select(GMSession).where(
            GMSession.id == session_id,
            GMSession.organization_id == org_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="GM session not found")
    return session
