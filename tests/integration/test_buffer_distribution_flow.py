"""Integration tests for Buffer Distribution Layer — DB-backed API tests."""
from __future__ import annotations

import pytest

from tests.conftest import create_brand_with_offer, register_and_login

pytestmark = pytest.mark.asyncio


async def test_create_and_list_buffer_profiles(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(
        f"/api/v1/brands/{bid}/buffer-profiles",
        json={"display_name": "TikTok Main", "platform": "tiktok"},
        headers=headers,
    )
    assert resp.status_code == 201
    profile = resp.json()
    assert profile["display_name"] == "TikTok Main"
    assert profile["platform"] == "tiktok"
    assert profile["credential_status"] == "not_connected"
    profile_id = profile["id"]

    resp2 = await api_client.get(f"/api/v1/brands/{bid}/buffer-profiles", headers=headers)
    assert resp2.status_code == 200
    profiles = resp2.json()
    assert len(profiles) >= 1
    assert any(p["id"] == profile_id for p in profiles)


async def test_update_buffer_profile(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(
        f"/api/v1/brands/{bid}/buffer-profiles",
        json={"display_name": "IG Profile", "platform": "instagram"},
        headers=headers,
    )
    profile_id = resp.json()["id"]

    resp2 = await api_client.patch(
        f"/api/v1/buffer-profiles/{profile_id}",
        json={"credential_status": "connected", "buffer_profile_id": "buf_ext_123"},
        headers=headers,
    )
    assert resp2.status_code == 200
    updated = resp2.json()
    assert updated["credential_status"] == "connected"
    assert updated["buffer_profile_id"] == "buf_ext_123"


async def test_recompute_publish_jobs(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    await api_client.post(
        f"/api/v1/brands/{bid}/buffer-profiles",
        json={"display_name": "YT", "platform": "youtube"},
        headers=headers,
    )

    resp = await api_client.post(f"/api/v1/brands/{bid}/buffer-publish-jobs/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "jobs_created" in body.get("counts", {})


async def test_submit_job_fails_without_api_key(api_client, sample_org_data):
    """Without BUFFER_API_KEY set, submitting should fail and create a blocker."""
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    profile_resp = await api_client.post(
        f"/api/v1/brands/{bid}/buffer-profiles",
        json={"display_name": "TK", "platform": "tiktok"},
        headers=headers,
    )
    profile_resp.json()["id"]

    await api_client.post(f"/api/v1/brands/{bid}/buffer-publish-jobs/recompute", headers=headers)

    jobs_resp = await api_client.get(f"/api/v1/brands/{bid}/buffer-publish-jobs", headers=headers)
    jobs = jobs_resp.json()

    if len(jobs) > 0:
        job_id = jobs[0]["id"]
        submit_resp = await api_client.post(f"/api/v1/buffer-publish-jobs/{job_id}/submit", headers=headers)
        assert submit_resp.status_code == 200
        body = submit_resp.json()
        assert body["status"] == "failed"

        blockers_resp = await api_client.get(f"/api/v1/brands/{bid}/buffer-blockers", headers=headers)
        blockers = blockers_resp.json()
        assert len(blockers) >= 1
        types = [b["blocker_type"] for b in blockers]
        assert "missing_buffer_api_key" in types or "missing_buffer_credentials" in types


async def test_status_sync(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.post(f"/api/v1/brands/{bid}/buffer-status-sync/recompute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "jobs_checked" in body.get("counts", {})


async def test_buffer_blockers_listed(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    resp = await api_client.get(f"/api/v1/brands/{bid}/buffer-blockers", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_profile_creation_multiple_platforms(api_client, sample_org_data):
    headers = await register_and_login(api_client, sample_org_data)
    bid, _, _ = await create_brand_with_offer(api_client, headers)

    for platform in ["tiktok", "instagram", "youtube", "twitter", "linkedin", "reddit", "facebook"]:
        resp = await api_client.post(
            f"/api/v1/brands/{bid}/buffer-profiles",
            json={"display_name": f"Profile {platform}", "platform": platform},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["platform"] == platform

    resp = await api_client.get(f"/api/v1/brands/{bid}/buffer-profiles", headers=headers)
    assert len(resp.json()) == 7
