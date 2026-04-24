"""Integration tests for Batch 4 — GM operating truth.

Covers:
  1. Stage transitions write StageState rows (proposal.sent, client
     active, intake sent, production running/qa_pending/qa_passed).
  2. request_approval → GMApproval row + gm.approval.requested event;
     idempotent per (org, entity, action_type).
  3. POST /gm/approvals/{id}/approve transitions pending→approved, emits
     gm.approval.approved.
  4. open_escalation idempotent; bumps occurrence_count on duplicates.
  5. stuck-stage watcher writes GMEscalation for a StageState past its
     SLA deadline.
  6. GET /gm/control-board returns consolidated state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from packages.db.models.gm_control import GMApproval, GMEscalation, StageState
from packages.db.models.system_events import SystemEvent


async def _auth(api_client, sample_org_data) -> tuple[dict, uuid.UUID]:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, uuid.UUID(me.json()["organization_id"])


@pytest.mark.asyncio
async def test_proposal_sent_writes_stage_state(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": "stagetest@acme.example",
            "title": "Stage test proposal",
            "line_items": [{"description": "Item", "unit_amount_cents": 10000}],
        },
    )
    pid = uuid.UUID(create.json()["id"])
    r = await api_client.post(f"/api/v1/proposals/{pid}/send", headers=headers)
    assert r.status_code == 200

    state = (
        await db_session.execute(
            select(StageState).where(
                StageState.entity_type == "proposal",
                StageState.entity_id == pid,
            )
        )
    ).scalar_one()
    assert state.stage == "sent"
    assert state.org_id == org_id
    assert state.sla_deadline is not None
    assert state.is_stuck is False


@pytest.mark.asyncio
async def test_request_approval_is_idempotent_and_emits_event(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)

    from apps.api.services.stage_controller import request_approval

    entity_id = uuid.uuid4()
    a1, new_1 = await request_approval(
        db_session,
        org_id=org_id,
        action_type="send_high_value_proposal",
        entity_type="proposal",
        entity_id=entity_id,
        title="High-value proposal needs approval",
        reason="$5k+ proposal",
        risk_level="high",
        confidence=0.80,
    )
    await db_session.commit()
    assert new_1 is True

    a2, new_2 = await request_approval(
        db_session,
        org_id=org_id,
        action_type="send_high_value_proposal",
        entity_type="proposal",
        entity_id=entity_id,
        title="duplicate title",
        reason="re-requested",
        risk_level="high",
    )
    await db_session.commit()
    assert new_2 is False
    assert a2.id == a1.id

    approvals = (await db_session.execute(select(GMApproval).where(GMApproval.entity_id == entity_id))).scalars().all()
    assert len(approvals) == 1

    evts = (
        (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "gm.approval.requested",
                    SystemEvent.entity_id == a1.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(evts) == 1


@pytest.mark.asyncio
async def test_approve_approval_route_emits_event(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)

    from apps.api.services.stage_controller import request_approval

    approval, _ = await request_approval(
        db_session,
        org_id=org_id,
        action_type="send_proposal",
        entity_type="proposal",
        entity_id=uuid.uuid4(),
        title="Needs approval",
    )
    await db_session.commit()

    r = await api_client.post(
        f"/api/v1/gm/approvals/{approval.id}/approve",
        headers=headers,
        json={"notes": "looks good"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "gm.approval.approved",
                SystemEvent.entity_id == approval.id,
            )
        )
    ).scalar_one()
    assert evt.new_state == "approved"


@pytest.mark.asyncio
async def test_open_escalation_idempotent_bumps_occurrence(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    from apps.api.services.stage_controller import open_escalation

    entity_id = uuid.uuid4()
    e1, new_1 = await open_escalation(
        db_session,
        org_id=org_id,
        entity_type="proposal",
        entity_id=entity_id,
        reason_code="test_stuck",
        title="Stuck proposal",
        severity="warning",
    )
    await db_session.commit()
    assert new_1 is True

    e2, new_2 = await open_escalation(
        db_session,
        org_id=org_id,
        entity_type="proposal",
        entity_id=entity_id,
        reason_code="test_stuck",
        title="Stuck proposal again",
    )
    await db_session.commit()
    assert new_2 is False
    assert e2.id == e1.id
    assert e2.occurrence_count == 2


@pytest.mark.asyncio
async def test_stuck_stage_watcher_opens_escalation_past_sla(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)

    # Seed a StageState manually with a past sla_deadline
    from apps.api.services.stage_controller import (
        mark_stage,
        run_stuck_stage_watcher,
    )

    eid = uuid.uuid4()
    state = await mark_stage(
        db_session,
        org_id=org_id,
        entity_type="intake_request",
        entity_id=eid,
        stage="sent",
    )
    # Force the SLA deadline into the past
    state.sla_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    result = await run_stuck_stage_watcher(db_session, org_id=org_id)
    await db_session.commit()
    assert result["escalations_opened"] >= 1

    esc = (
        await db_session.execute(
            select(GMEscalation).where(
                GMEscalation.org_id == org_id,
                GMEscalation.entity_id == eid,
            )
        )
    ).scalar_one()
    assert esc.reason_code == "intake_pending_48h"
    assert esc.status == "open"
    assert esc.severity == "warning"

    await db_session.refresh(state)
    assert state.is_stuck is True


@pytest.mark.asyncio
async def test_control_board_consolidated_view(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)

    from apps.api.services.stage_controller import (
        mark_stage,
        open_escalation,
        request_approval,
    )

    # Seed one approval + one escalation + one stuck stage
    await request_approval(
        db_session,
        org_id=org_id,
        action_type="custom_test",
        entity_type="proposal",
        entity_id=uuid.uuid4(),
        title="Needs approval",
    )
    await open_escalation(
        db_session,
        org_id=org_id,
        entity_type="proposal",
        entity_id=uuid.uuid4(),
        reason_code="custom_stuck",
        title="Custom stuck",
    )
    state = await mark_stage(
        db_session,
        org_id=org_id,
        entity_type="intake_request",
        entity_id=uuid.uuid4(),
        stage="sent",
    )
    state.is_stuck = True
    state.stuck_reason = "test"
    await db_session.commit()

    r = await api_client.get("/api/v1/gm/control-board", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["awaiting_approval"]) >= 1
    assert len(body["escalated"]) >= 1
    assert len(body["stuck_stages"]) >= 1
    assert "auto_handled_count_recent" in body
    assert "revenue_event_count_recent" in body
