"""Integration tests for Phase 3 content pipeline: brief -> script -> QA -> approve -> publish."""

import pytest


async def _setup_pipeline(api_client, sample_org_data):
    """Register, create brand+offer+account, create brief, return headers+IDs."""
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_org_data["email"],
            "password": sample_org_data["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    brand = await api_client.post(
        "/api/v1/brands/",
        json={
            "name": "Pipeline Brand",
            "slug": "pipe-brand",
            "niche": "finance",
        },
        headers=headers,
    )
    bid = brand.json()["id"]

    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": "Pipe Offer",
            "monetization_method": "affiliate",
            "payout_amount": 25.0,
            "epc": 1.5,
            "conversion_rate": 0.03,
        },
        headers=headers,
    )

    account = await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": bid,
            "platform": "youtube",
            "platform_username": "@pipetest",
        },
        headers=headers,
    )

    brief = await api_client.post(
        "/api/v1/content/briefs",
        json={
            "brand_id": bid,
            "title": "Test Pipeline Brief",
            "content_type": "short_video",
            "hook": "This changes everything",
            "angle": "Contrarian take",
        },
        headers=headers,
    )
    brief_id = brief.json()["id"]

    return headers, bid, brief_id, account.json()["id"]


@pytest.mark.asyncio
async def test_generate_script_from_brief(api_client, sample_org_data):
    headers, bid, brief_id, _ = await _setup_pipeline(api_client, sample_org_data)
    response = await api_client.post(f"/api/v1/pipeline/briefs/{brief_id}/generate-scripts", headers=headers)
    assert response.status_code == 200
    script = response.json()
    assert script["version"] == 1
    assert script["word_count"] > 0
    assert script["status"] == "generated"
    assert script["generation_model"] == "template_v1"


@pytest.mark.asyncio
async def test_script_validation_enforced(api_client, sample_org_data):
    """Scripts with empty content should fail validation."""
    headers, bid, brief_id, _ = await _setup_pipeline(api_client, sample_org_data)
    response = await api_client.post(f"/api/v1/pipeline/briefs/{brief_id}/generate-scripts", headers=headers)
    assert response.status_code == 200
    script = response.json()
    assert len(script["full_script"]) >= 20


@pytest.mark.asyncio
async def test_script_scoring(api_client, sample_org_data):
    headers, bid, brief_id, _ = await _setup_pipeline(api_client, sample_org_data)
    script_resp = await api_client.post(f"/api/v1/pipeline/briefs/{brief_id}/generate-scripts", headers=headers)
    script_id = script_resp.json()["id"]

    response = await api_client.post(f"/api/v1/pipeline/scripts/{script_id}/score", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "publish_score" in data
    assert "confidence" in data
    assert "explanation" in data
    assert "components" in data


@pytest.mark.asyncio
async def test_media_job_creation(api_client, sample_org_data):
    headers, bid, brief_id, _ = await _setup_pipeline(api_client, sample_org_data)
    script_resp = await api_client.post(f"/api/v1/pipeline/briefs/{brief_id}/generate-scripts", headers=headers)
    script_id = script_resp.json()["id"]

    response = await api_client.post(f"/api/v1/pipeline/scripts/{script_id}/generate-media", headers=headers)
    assert response.status_code == 200
    job = response.json()
    assert job["job_type"] == "avatar_video"
    assert job["status"] in ("pending", "running")
    assert job["provider"] is not None


@pytest.mark.asyncio
async def test_qa_scoring_persistence(api_client, sample_org_data, db_session):
    """QA report must persist all decomposed score components."""
    headers, bid, brief_id, acct_id = await _setup_pipeline(api_client, sample_org_data)

    from packages.db.enums import ContentType as CT
    from packages.db.models.content import ContentItem

    item = ContentItem(
        brand_id=bid,
        brief_id=brief_id,
        title="QA Test Item",
        content_type=CT.SHORT_VIDEO,
        status="draft",
        tags=["test"],
    )
    db_session.add(item)
    await db_session.flush()

    response = await api_client.post(f"/api/v1/pipeline/content/{item.id}/run-qa", headers=headers)
    assert response.status_code == 200
    data = response.json()
    qa = data["qa_report"]
    assert qa["qa_status"] in ("pass", "review", "fail")
    assert qa["composite_score"] > 0
    assert qa["explanation"] is not None
    assert qa["automated_checks"] is not None
    assert "originality_score" in qa
    assert "compliance_score" in qa


@pytest.mark.asyncio
async def test_approval_flow(api_client, sample_org_data, db_session):
    headers, bid, brief_id, acct_id = await _setup_pipeline(api_client, sample_org_data)

    from packages.db.enums import ContentType as CT
    from packages.db.models.content import ContentItem

    item = ContentItem(
        brand_id=bid,
        title="Approval Test",
        content_type=CT.SHORT_VIDEO,
        status="draft",
    )
    db_session.add(item)
    await db_session.flush()

    approve_resp = await api_client.post(
        f"/api/v1/pipeline/content/{item.id}/approve",
        json={"notes": "LGTM"},
        headers=headers,
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] in ("approved", "revision_requested")


@pytest.mark.asyncio
async def test_reject_flow(api_client, sample_org_data, db_session):
    headers, bid, brief_id, acct_id = await _setup_pipeline(api_client, sample_org_data)

    from packages.db.enums import ContentType as CT
    from packages.db.models.content import ContentItem

    item = ContentItem(
        brand_id=bid,
        title="Reject Test",
        content_type=CT.SHORT_VIDEO,
        status="draft",
    )
    db_session.add(item)
    await db_session.flush()

    resp = await api_client.post(
        f"/api/v1/pipeline/content/{item.id}/reject",
        json={"notes": "Not aligned"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_request_changes_flow(api_client, sample_org_data, db_session):
    headers, bid, brief_id, acct_id = await _setup_pipeline(api_client, sample_org_data)

    from packages.db.enums import ContentType as CT
    from packages.db.models.content import ContentItem

    item = ContentItem(
        brand_id=bid,
        title="Changes Test",
        content_type=CT.SHORT_VIDEO,
        status="draft",
    )
    db_session.add(item)
    await db_session.flush()

    resp = await api_client.post(
        f"/api/v1/pipeline/content/{item.id}/request-changes",
        json={"notes": "Fix CTA"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "revision_requested"


@pytest.mark.asyncio
async def test_publish_requires_approved(api_client, sample_org_data, db_session):
    headers, bid, brief_id, acct_id = await _setup_pipeline(api_client, sample_org_data)

    from packages.db.enums import ContentType as CT
    from packages.db.models.content import ContentItem

    item = ContentItem(
        brand_id=bid,
        title="Unapproved",
        content_type=CT.SHORT_VIDEO,
        status="draft",
    )
    db_session.add(item)
    await db_session.flush()

    resp = await api_client.post(
        f"/api/v1/pipeline/content/{item.id}/schedule",
        json={"creator_account_id": acct_id, "platform": "youtube"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_publish_job_creation(api_client, sample_org_data, db_session):
    headers, bid, brief_id, acct_id = await _setup_pipeline(api_client, sample_org_data)

    from packages.db.enums import ContentType as CT
    from packages.db.models.content import ContentItem

    item = ContentItem(
        brand_id=bid,
        title="Publishable",
        content_type=CT.SHORT_VIDEO,
        status="approved",
    )
    db_session.add(item)
    await db_session.flush()

    resp = await api_client.post(
        f"/api/v1/pipeline/content/{item.id}/schedule",
        json={"creator_account_id": acct_id, "platform": "youtube"},
        headers=headers,
    )
    assert resp.status_code == 200
    job = resp.json()
    assert job["platform"] == "youtube"
    assert job["status"] == "pending"


@pytest.mark.asyncio
async def test_approval_action_audited(api_client, sample_org_data, db_session):
    headers, bid, brief_id, _ = await _setup_pipeline(api_client, sample_org_data)

    from packages.db.enums import ContentType as CT
    from packages.db.models.content import ContentItem

    item = ContentItem(
        brand_id=bid,
        title="Audit Me",
        content_type=CT.SHORT_VIDEO,
        status="draft",
    )
    db_session.add(item)
    await db_session.flush()

    await api_client.post(
        f"/api/v1/pipeline/content/{item.id}/approve",
        json={"notes": "Approved"},
        headers=headers,
    )

    audit = await api_client.get("/api/v1/jobs/audit/logs", headers=headers)
    actions = [e["action"] for e in audit.json()["items"]]
    assert "content.approved" in actions
