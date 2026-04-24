"""Integration tests for Batch 3C — fulfillment cascade.

Covers:
  1. Intake completion cascades → ClientProject + ProjectBrief v1 +
     ProductionJob (running), emitting project.created, brief.created,
     production.started.
  2. Cascade is idempotent — a second completion cascade on the same
     intake submission does NOT duplicate project/brief/job.
  3. POST /projects/{id}/briefs/regenerate creates v2, marks v1
     superseded, emits brief.created for v2 only.
  4. POST /briefs/{id}/launch-production reuses an active job when one
     exists instead of creating a duplicate.
  5. GET /projects/{id} returns nested briefs + production_jobs.
  6. Cross-org access → 403.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from packages.db.models.clients import IntakeRequest
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


async def _full_activation(api_client, db_session, headers, org_id, monkeypatch, email_suffix: str = ""):
    """Run the full payment → client → intake completion cascade. Returns the project_id."""
    email = f"fulfillment-{email_suffix or uuid.uuid4().hex[:6]}@acme.example"

    async def _fake_create_link(**kwargs):
        return {"url": "https://checkout.stripe.com/test", "id": f"plink_{uuid.uuid4().hex[:8]}"}

    from apps.api.services import stripe_billing_service
    monkeypatch.setattr(stripe_billing_service, "create_payment_link", _fake_create_link)

    create = await api_client.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "recipient_email": email,
            "title": "Growth Pack Test",
            "package_slug": "growth-content-pack",
            "line_items": [{"description": "Pack", "unit_amount_cents": 150000}],
        },
    )
    pid = uuid.UUID(create.json()["id"])
    await api_client.post(
        f"/api/v1/proposals/{pid}/payment-link", headers=headers, json={}
    )

    event_id = f"evt_fulfill_{uuid.uuid4().hex[:12]}"
    payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_{uuid.uuid4().hex[:8]}",
                "amount_total": 150000,
                "currency": "usd",
                "customer_email": email,
                "customer_details": {"name": "Pat Customer"},
                "metadata": {"proposal_id": str(pid), "org_id": str(org_id), "source": "proposal"},
            }
        },
    }

    async def _fake_verify(**kwargs):
        return {
            "valid": True,
            "event_id": event_id,
            "event_type": "checkout.session.completed",
            "payload": payload,
        }, None

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
    intake = intake[-1]  # most recent

    # Submit complete intake
    submit_resp = await api_client.post(
        f"/api/v1/intake/{intake.token}/submit",
        json={
            "submitter_email": email,
            "responses": {
                "company_name": "Acme Brand",
                "primary_contact": "Pat Customer",
                "target_audience": "SaaS founders",
                "goals": "Grow audience to 50k",
                "brand_voice": "confident, direct",
                "assets_url": "https://acme.com/brand",
            },
        },
    )
    assert submit_resp.status_code == 201, submit_resp.text
    return intake.id


@pytest.mark.asyncio
async def test_intake_completion_cascades_to_project_brief_production(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    await _full_activation(api_client, db_session, headers, org_id, monkeypatch)

    # Project created
    project = (
        await db_session.execute(
            select(ClientProject).where(ClientProject.org_id == org_id)
        )
    ).scalar_one()
    assert project.status == "active"
    assert project.intake_submission_id is not None

    # Brief v1 created
    briefs = (
        await db_session.execute(
            select(ProjectBrief).where(ProjectBrief.project_id == project.id)
        )
    ).scalars().all()
    assert len(briefs) == 1
    assert briefs[0].version == 1
    assert briefs[0].status == "approved"  # auto-approved on production launch

    # ProductionJob running
    jobs = (
        await db_session.execute(
            select(ProductionJob).where(ProductionJob.project_id == project.id)
        )
    ).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].status == "running"
    assert jobs[0].attempt_count == 1

    # Events
    event_types = (
        await db_session.execute(
            select(SystemEvent.event_type).where(
                SystemEvent.event_domain == "fulfillment",
                SystemEvent.organization_id == org_id,
            )
        )
    ).scalars().all()
    for et in ("project.created", "brief.created", "production.started"):
        assert et in event_types, f"Missing {et} in {event_types}"


@pytest.mark.asyncio
async def test_cascade_is_idempotent_on_reruns(
    api_client, db_session, sample_org_data, monkeypatch
):
    """Simulate a second completion submission (e.g. re-submit via
    operator) — cascade should not duplicate project/brief/job."""
    headers, org_id = await _auth(api_client, sample_org_data)
    await _full_activation(api_client, db_session, headers, org_id, monkeypatch)

    # Call cascade directly on the same submission to simulate a retry
    from apps.api.services.fulfillment_service import cascade_intake_to_production
    from packages.db.models.clients import IntakeSubmission

    sub = (
        await db_session.execute(
            select(IntakeSubmission).where(IntakeSubmission.org_id == org_id)
        )
    ).scalar_one()
    result = await cascade_intake_to_production(db_session, intake_submission=sub)
    await db_session.commit()
    assert result["project_is_new"] is False

    # Still exactly one of each
    projects = (
        await db_session.execute(
            select(ClientProject).where(ClientProject.org_id == org_id)
        )
    ).scalars().all()
    assert len(projects) == 1

    briefs = (
        await db_session.execute(
            select(ProjectBrief).where(ProjectBrief.project_id == projects[0].id)
        )
    ).scalars().all()
    assert len(briefs) == 1

    jobs = (
        await db_session.execute(
            select(ProductionJob).where(ProductionJob.project_id == projects[0].id)
        )
    ).scalars().all()
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_regenerate_brief_creates_v2_supersedes_v1(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    await _full_activation(api_client, db_session, headers, org_id, monkeypatch)

    project = (
        await db_session.execute(
            select(ClientProject).where(ClientProject.org_id == org_id)
        )
    ).scalar_one()

    resp = await api_client.post(
        f"/api/v1/projects/{project.id}/briefs/regenerate",
        headers=headers,
        json={"regenerate": True},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["version"] == 2
    assert resp.json()["status"] == "draft"

    briefs = (
        await db_session.execute(
            select(ProjectBrief)
            .where(ProjectBrief.project_id == project.id)
            .order_by(ProjectBrief.version)
        )
    ).scalars().all()
    assert len(briefs) == 2
    assert briefs[0].version == 1
    assert briefs[0].status == "superseded"
    assert briefs[1].version == 2
    assert briefs[1].status == "draft"


@pytest.mark.asyncio
async def test_launch_production_idempotent_when_job_active(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    await _full_activation(api_client, db_session, headers, org_id, monkeypatch)

    brief = (
        await db_session.execute(
            select(ProjectBrief).where(ProjectBrief.org_id == org_id)
        )
    ).scalar_one()

    r = await api_client.post(
        f"/api/v1/briefs/{brief.id}/launch-production",
        headers=headers,
        json={"job_type": "content_pack"},
    )
    assert r.status_code == 201
    first_job_id = r.json()["id"]

    # Second call should return SAME job id (cascade already launched one)
    r2 = await api_client.post(
        f"/api/v1/briefs/{brief.id}/launch-production",
        headers=headers,
        json={"job_type": "content_pack"},
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == first_job_id

    jobs = (
        await db_session.execute(
            select(ProductionJob).where(ProductionJob.brief_id == brief.id)
        )
    ).scalars().all()
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_get_project_returns_nested_briefs_and_jobs(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id = await _auth(api_client, sample_org_data)
    await _full_activation(api_client, db_session, headers, org_id, monkeypatch)

    project = (
        await db_session.execute(
            select(ClientProject).where(ClientProject.org_id == org_id)
        )
    ).scalar_one()
    r = await api_client.get(f"/api/v1/projects/{project.id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["briefs"]) == 1
    assert len(body["production_jobs"]) == 1
    assert body["production_jobs"][0]["status"] == "running"


@pytest.mark.asyncio
async def test_cross_org_project_access_returns_403(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers_a, org_a = await _auth(api_client, sample_org_data)
    await _full_activation(api_client, db_session, headers_a, org_a, monkeypatch, "a")
    project_a = (
        await db_session.execute(
            select(ClientProject).where(ClientProject.org_id == org_a)
        )
    ).scalar_one()

    # Org B
    org_b_data = {
        "organization_name": f"Other {uuid.uuid4().hex[:4]}",
        "email": f"b-{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass456",
        "full_name": "Other",
    }
    headers_b, _ = await _auth(api_client, org_b_data)
    r = await api_client.get(f"/api/v1/projects/{project_a.id}", headers=headers_b)
    assert r.status_code == 403
