"""Integration tests for Batch 3D — QA loop + delivery + followup.

Covers:
  1. submit-output → auto-QA pass → auto-dispatch → delivery.sent +
     followup.scheduled events.
  2. Force-fail QA on a job with retry_limit=2 → job goes back to
     status=running, attempt_count=2, qa.failed event with
     terminal=False.
  3. Retry path exhausted: fail twice → job status=failed,
     qa.failed event with terminal=True.
  4. Manual dispatch-delivery after qa_passed → writes Delivery,
     transitions job to completed.
  5. Idempotency: second dispatch returns same delivery.
  6. Project completes when its last job ships.
  7. Reschedule followup emits fresh followup.scheduled event.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from packages.db.models.clients import IntakeRequest
from packages.db.models.delivery import Delivery, ProductionQAReview
from packages.db.models.fulfillment import ClientProject, ProductionJob, ProjectBrief
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


async def _activate_and_get_job(api_client, db_session, headers, org_id, monkeypatch) -> ProductionJob:
    email = f"qa-{uuid.uuid4().hex[:6]}@acme.example"

    async def _fake_create_link(**kwargs):
        return {"url": "https://checkout.stripe.com/test", "id": f"plink_{uuid.uuid4().hex[:8]}"}

    from apps.api.services import stripe_billing_service
    monkeypatch.setattr(stripe_billing_service, "create_payment_link", _fake_create_link)

    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": email,
            "title": "QA flow test pack",
            "line_items": [{"description": "Pack", "unit_amount_cents": 100000}],
        },
    )
    pid = uuid.UUID(create.json()["id"])
    await api_client.post(
        f"/api/v1/proposals/{pid}/payment-link", headers=headers, json={}
    )

    event_id = f"evt_qa_{uuid.uuid4().hex[:12]}"
    payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_{uuid.uuid4().hex[:8]}",
                "amount_total": 100000,
                "currency": "usd",
                "customer_email": email,
                "customer_details": {"name": "QA Test"},
                "metadata": {"proposal_id": str(pid), "org_id": str(org_id), "source": "proposal"},
            }
        },
    }

    async def _fake_verify(**kwargs):
        return {"valid": True, "event_id": event_id,
                "event_type": "checkout.session.completed", "payload": payload}, None

    from apps.api.routers import webhooks as webhooks_mod
    monkeypatch.setattr(webhooks_mod, "_verify_webhook_with_candidates", _fake_verify)

    await api_client.post(
        "/api/v1/webhooks/stripe", headers={"Stripe-Signature": "fake"}, content=b"{}"
    )

    intake = (
        await db_session.execute(
            select(IntakeRequest).where(IntakeRequest.org_id == org_id)
        )
    ).scalars().all()
    intake = intake[-1]

    await api_client.post(
        f"/api/v1/intake/{intake.token}/submit",
        json={
            "submitter_email": email,
            "responses": {
                "company_name": "QA Acme",
                "primary_contact": "Pat",
                "target_audience": "SaaS",
                "goals": "Grow",
            },
        },
    )

    # Fetch the running production job
    job = (
        await db_session.execute(
            select(ProductionJob).where(ProductionJob.org_id == org_id)
        )
    ).scalar_one()
    return job


@pytest.mark.asyncio
async def test_submit_output_auto_qa_pass_auto_dispatches(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    job = await _activate_and_get_job(api_client, db_session, headers, org_id, monkeypatch)

    resp = await api_client.post(
        f"/api/v1/production-jobs/{job.id}/submit-output",
        headers=headers,
        json={
            "output_url": "https://cdn.example/pack-001.zip",
            "auto_qa": True,
            "auto_dispatch": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["qa"]["result"] == "passed"
    assert body["delivery"]["status"] == "sent"
    assert body["delivery"]["followup_scheduled_at"]

    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.output_url == "https://cdn.example/pack-001.zip"

    # Events: qa.passed, delivery.sent, followup.scheduled
    evt_types = (
        await db_session.execute(
            select(SystemEvent.event_type).where(
                SystemEvent.event_domain == "fulfillment",
                SystemEvent.organization_id == org_id,
                SystemEvent.event_type.in_(("qa.passed", "delivery.sent", "followup.scheduled")),
            )
        )
    ).scalars().all()
    assert "qa.passed" in evt_types
    assert "delivery.sent" in evt_types
    assert "followup.scheduled" in evt_types

    # Delivery row exists
    delivery = (
        await db_session.execute(
            select(Delivery).where(Delivery.production_job_id == job.id)
        )
    ).scalar_one()
    assert delivery.status == "sent"
    assert delivery.followup_scheduled_at is not None


@pytest.mark.asyncio
async def test_force_fail_qa_retries_within_limit(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    job = await _activate_and_get_job(api_client, db_session, headers, org_id, monkeypatch)
    # retry_limit default is 2; attempt_count starts at 1
    # First force-fail → retry: status=running, attempt_count=2
    job.status = "qa_pending"
    await db_session.commit()

    r = await api_client.post(
        f"/api/v1/production-jobs/{job.id}/qa-review",
        headers=headers,
        json={"scores": {"composite": 0.5}, "force_fail": True, "notes": "Too sparse"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["result"] == "failed"
    assert r.json()["job_status_after"] == "running"
    assert r.json()["job_attempt_count_after"] == 2

    # qa.failed event with terminal=False
    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "qa.failed",
                SystemEvent.entity_id == job.id,
            )
        )
    ).scalar_one()
    assert evt.details["terminal"] is False
    assert evt.new_state == "running"


@pytest.mark.asyncio
async def test_retry_exhausted_marks_job_failed(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    job = await _activate_and_get_job(api_client, db_session, headers, org_id, monkeypatch)
    job.status = "qa_pending"
    await db_session.commit()

    # First fail → retry
    await api_client.post(
        f"/api/v1/production-jobs/{job.id}/qa-review",
        headers=headers,
        json={"force_fail": True, "notes": "first fail"},
    )
    # Second fail → terminal (attempt_count reached retry_limit + 1 after increment)
    await db_session.refresh(job)
    job.status = "qa_pending"
    await db_session.commit()
    r = await api_client.post(
        f"/api/v1/production-jobs/{job.id}/qa-review",
        headers=headers,
        json={"force_fail": True, "notes": "second fail"},
    )
    assert r.json()["job_status_after"] == "failed"

    await db_session.refresh(job)
    assert job.status == "failed"

    # At least one qa.failed with terminal=True
    evts = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "qa.failed",
                SystemEvent.entity_id == job.id,
            )
        )
    ).scalars().all()
    assert any(e.details.get("terminal") is True for e in evts)


@pytest.mark.asyncio
async def test_manual_dispatch_delivery_after_qa_passed(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    job = await _activate_and_get_job(api_client, db_session, headers, org_id, monkeypatch)

    # Submit output with auto_qa=True but auto_dispatch=False
    await api_client.post(
        f"/api/v1/production-jobs/{job.id}/submit-output",
        headers=headers,
        json={
            "output_url": "https://cdn.example/pack.zip",
            "auto_qa": True,
            "auto_dispatch": False,
        },
    )
    await db_session.refresh(job)
    assert job.status == "qa_passed"

    # Dispatch manually
    r = await api_client.post(
        f"/api/v1/production-jobs/{job.id}/dispatch-delivery",
        headers=headers,
        json={"channel": "email", "followup_days": 3},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "sent"

    await db_session.refresh(job)
    assert job.status == "completed"

    # Second dispatch returns the SAME delivery (idempotent)
    r2 = await api_client.post(
        f"/api/v1/production-jobs/{job.id}/dispatch-delivery",
        headers=headers,
        json={"channel": "email"},
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == r.json()["id"]


@pytest.mark.asyncio
async def test_project_marked_completed_when_all_jobs_done(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    job = await _activate_and_get_job(api_client, db_session, headers, org_id, monkeypatch)

    await api_client.post(
        f"/api/v1/production-jobs/{job.id}/submit-output",
        headers=headers,
        json={"output_url": "https://cdn.example/out.zip"},
    )

    project = (
        await db_session.execute(
            select(ClientProject).where(ClientProject.id == job.project_id)
        )
    ).scalar_one()
    await db_session.refresh(project)
    assert project.status == "completed"
    assert project.completed_at is not None


@pytest.mark.asyncio
async def test_reschedule_followup_emits_event(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    job = await _activate_and_get_job(api_client, db_session, headers, org_id, monkeypatch)

    await api_client.post(
        f"/api/v1/production-jobs/{job.id}/submit-output",
        headers=headers,
        json={"output_url": "https://cdn.example/x.zip"},
    )
    delivery = (
        await db_session.execute(
            select(Delivery).where(Delivery.production_job_id == job.id)
        )
    ).scalar_one()

    new_when = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    r = await api_client.post(
        f"/api/v1/deliveries/{delivery.id}/schedule-followup",
        headers=headers,
        json={"followup_scheduled_at": new_when},
    )
    assert r.status_code == 200
    await db_session.refresh(delivery)
    assert delivery.followup_scheduled_at is not None

    evts = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "followup.scheduled",
                SystemEvent.entity_id == delivery.id,
            )
        )
    ).scalars().all()
    # At least 2 followup.scheduled events (original + reschedule)
    assert len(evts) >= 2
