"""Operator dashboard endpoints — list / detail / mark-qualified / archive.

Reuses the auth fixtures from conftest. Seeds an Organization + Brand so
the public test endpoint can attribute the lead, then asserts the operator
endpoints serve, filter, and mutate as expected.
"""

from __future__ import annotations

import uuid

import pytest

import packages.db.models  # noqa: F401
import packages.db.models.authority_score_reports  # noqa: F401
import packages.db.models.clients  # noqa: F401
import packages.db.models.delivery  # noqa: F401
import packages.db.models.expansion_pack2_phase_a  # noqa: F401
import packages.db.models.fulfillment  # noqa: F401
import packages.db.models.gm_control  # noqa: F401
import packages.db.models.live_execution_phase2  # noqa: F401
import packages.db.models.proposals  # noqa: F401
import packages.db.models.system_events  # noqa: F401
from packages.db.models.core import Brand, Organization
from tests.integration.test_ai_buyer_trust_flow import (  # noqa: E402 — reuse fixture helpers
    _patch_scanner,
)


async def _register_and_login_proofhook(api_client, db_session, sample_org_data):
    """Register the operator. Then rename the resulting org/brand so the
    DB-backed `resolve_proofhook_org_and_brand` can find them by slug."""
    reg = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert reg.status_code == 201, reg.text
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    org_id = uuid.UUID(me.json()["organization_id"])
    # Promote this org to canonical 'proofhook' so the resolver picks it.
    from sqlalchemy import select

    org = (await db_session.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
    org.slug = "proofhook"
    org.name = "ProofHook"
    brand = Brand(organization_id=org.id, name="ProofHook", slug="proofhook", niche="b2b", is_active=True)
    db_session.add(brand)
    await db_session.flush()
    await db_session.commit()
    return headers, org.id, brand.id


@pytest.mark.asyncio
async def test_dashboard_list_and_detail(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id, _brand_id = await _register_and_login_proofhook(api_client, db_session, sample_org_data)
    _patch_scanner(monkeypatch)

    # Submit one report via the public endpoint
    sub = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json={
            "website_url": "https://acme.io",
            "company_name": "Acme",
            "industry": "B2B SaaS",
            "contact_email": "pat@acme.io",
        },
    )
    assert sub.status_code == 200
    report_id = sub.json()["report_id"]

    # Operator list
    listing = await api_client.get("/api/v1/ai-search-authority/reports?limit=10", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    matched = next(i for i in body["items"] if i["id"] == report_id)
    assert matched["company_name"] == "Acme"
    assert matched["recommended_package_slug"]
    assert matched["report_status"] == "scored"

    # Operator detail
    detail = await api_client.get(f"/api/v1/ai-search-authority/reports/{report_id}", headers=headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["company_name"] == "Acme"
    assert isinstance(d["dimension_scores"], dict)
    assert isinstance(d["evidence"], dict)
    assert isinstance(d["authority_graph"], dict)
    assert isinstance(d["buyer_questions"], list) and len(d["buyer_questions"]) >= 5
    assert isinstance(d["recommended_pages"], list)
    assert isinstance(d["recommended_schema"], list)
    assert isinstance(d["recommended_proof_assets"], list)
    assert isinstance(d["recommended_comparison_surfaces"], list)
    assert d["formula_version"] == "v1"
    assert d["report_version"] == "v1"
    assert d["scan_version"] == "v1"


@pytest.mark.asyncio
async def test_mark_qualified_and_archive(api_client, db_session, sample_org_data, monkeypatch):
    headers, _, _ = await _register_and_login_proofhook(api_client, db_session, sample_org_data)
    _patch_scanner(monkeypatch)
    sub = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json={
            "website_url": "https://acme.io",
            "company_name": "Acme",
            "industry": "B2B SaaS",
            "contact_email": "pat@acme.io",
        },
    )
    report_id = sub.json()["report_id"]

    qual = await api_client.post(f"/api/v1/ai-search-authority/reports/{report_id}/mark-qualified", headers=headers)
    assert qual.status_code == 200
    assert qual.json()["report_status"] == "qualified"

    arch = await api_client.post(f"/api/v1/ai-search-authority/reports/{report_id}/archive", headers=headers)
    assert arch.status_code == 200
    assert arch.json()["report_status"] == "archived"


@pytest.mark.asyncio
async def test_unauthenticated_list_is_rejected(api_client, db_session):
    # No Authorization header → 401
    r = await api_client.get("/api/v1/ai-search-authority/reports")
    assert r.status_code in (401, 403)
