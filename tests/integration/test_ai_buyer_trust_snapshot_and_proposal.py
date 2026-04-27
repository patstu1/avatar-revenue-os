"""Snapshot review request + proposal handoff endpoints.

- POST /reports/{id}/request-snapshot-review (public)
- POST /reports/{id}/create-proposal (operator auth)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

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
from packages.db.models.authority_score_reports import AuthorityScoreReport
from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
from packages.db.models.proposals import Proposal
from packages.db.models.system_events import OperatorAction, SystemEvent
from tests.integration.test_ai_buyer_trust_dashboard import (  # noqa: E402
    _register_and_login_proofhook,
)
from tests.integration.test_ai_buyer_trust_flow import _patch_scanner  # noqa: E402


async def _submit_test(api_client, db_session) -> dict:
    r = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json={
            "website_url": "https://acme.io",
            "company_name": "Acme",
            "industry": "B2B SaaS",
            "contact_email": "pat@acme.io",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body


# ─────────────────────────────────────────────────────────────────────
# /request-snapshot-review (public)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_review_request_flips_status_and_emits_action(
    api_client, db_session, sample_org_data, monkeypatch
):
    headers, org_id, _brand_id = await _register_and_login_proofhook(api_client, db_session, sample_org_data)
    _patch_scanner(monkeypatch)

    submitted = await _submit_test(api_client, db_session)
    report_id = submitted["report_id"]

    # Public endpoint, no auth needed
    r = await api_client.post(f"/api/v1/ai-search-authority/reports/{report_id}/request-snapshot-review")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report_status"] == "snapshot_review_requested"
    assert "queued for operator review" in body["message"].lower()

    # Status persisted
    row = (
        await db_session.execute(select(AuthorityScoreReport).where(AuthorityScoreReport.id == uuid.UUID(report_id)))
    ).scalar_one()
    assert row.report_status == "snapshot_review_requested"

    # OperatorAction emitted with the snapshot-request action_type
    action = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.organization_id == org_id,
                OperatorAction.action_type == "review_buyer_trust_snapshot_request",
                OperatorAction.entity_id == row.id,
            )
        )
    ).scalar_one_or_none()
    assert action is not None, "Snapshot request must emit an OperatorAction"
    assert action.priority == "high"

    # SystemEvent emitted
    ev = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "ai_buyer_trust.snapshot_review_requested",
                SystemEvent.entity_id == row.id,
            )
        )
    ).scalar_one_or_none()
    assert ev is not None


@pytest.mark.asyncio
async def test_snapshot_review_request_404_for_unknown_report(api_client, db_session, sample_org_data, monkeypatch):
    await _register_and_login_proofhook(api_client, db_session, sample_org_data)
    bogus = uuid.uuid4()
    r = await api_client.post(f"/api/v1/ai-search-authority/reports/{bogus}/request-snapshot-review")
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# /create-proposal (operator auth)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_proposal_from_report(api_client, db_session, sample_org_data, monkeypatch):
    headers, org_id, brand_id = await _register_and_login_proofhook(api_client, db_session, sample_org_data)
    _patch_scanner(monkeypatch)

    submitted = await _submit_test(api_client, db_session)
    report_id = submitted["report_id"]

    # Reload to confirm a recommended_package_slug was persisted
    row = (
        await db_session.execute(select(AuthorityScoreReport).where(AuthorityScoreReport.id == uuid.UUID(report_id)))
    ).scalar_one()
    assert row.recommended_package_slug, "scored report must have a primary slug"

    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/create-proposal",
        json={},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proposal_id"]
    assert body["package_slug"] == row.recommended_package_slug
    assert body["report_status"] == "proposal_created"
    assert body["proposal_url"].startswith("/dashboard/proposals/")

    # Proposal row exists with the right shape
    proposal = (
        await db_session.execute(select(Proposal).where(Proposal.id == uuid.UUID(body["proposal_id"])))
    ).scalar_one()
    assert proposal.org_id == org_id
    assert proposal.brand_id == brand_id
    assert proposal.recipient_email == "pat@acme.io"
    assert proposal.package_slug == row.recommended_package_slug
    assert proposal.status == "draft"
    assert (proposal.extra_json or {}).get("ai_buyer_trust_report_id") == report_id

    # Linked LeadOpportunity sales_stage updated
    if row.lead_opportunity_id:
        lead = (
            await db_session.execute(select(LeadOpportunity).where(LeadOpportunity.id == row.lead_opportunity_id))
        ).scalar_one()
        assert lead.sales_stage == "proposal_sent"


@pytest.mark.asyncio
async def test_create_proposal_with_creative_companion(api_client, db_session, sample_org_data, monkeypatch):
    """When the report carries a creative_proof_slug AND the operator
    opts in, the proposal includes a second line item for the creative
    companion. Use a low-proof scenario so the engine recommends one."""
    from apps.api.services import ai_buyer_trust_service as svc
    from apps.api.services import website_scanner as ws

    headers, _, _ = await _register_and_login_proofhook(api_client, db_session, sample_org_data)

    # Force a thin homepage to surface a creative companion (proof_strength
    # will be very low → engine recommends signal_entry).
    thin_html = b"<html><body><h1>Acme</h1><p>We do stuff.</p></body></html>"

    async def fake_scan(homepage_url: str):
        result = ws.ScanResult(homepage_url=homepage_url)
        page = ws.parse_html_into_page(thin_html, homepage_url)
        result.pages.append(page)
        result.robots_txt_present = False
        result.sitemap_present = False
        return result

    monkeypatch.setattr(ws, "scan_website", fake_scan)
    monkeypatch.setattr(svc, "scan_website", fake_scan)

    submitted = await _submit_test(api_client, db_session)
    report_id = submitted["report_id"]
    # Confirm the engine recommended a creative companion for this thin site
    assert submitted["recommended_package"]["creative_proof_slug"] is not None, (
        f"Test setup expected a thin site to trigger a creative companion; got: {submitted['recommended_package']}"
    )

    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/create-proposal",
        json={"include_creative_companion": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["creative_proof_slug"] is not None

    proposal = (
        await db_session.execute(select(Proposal).where(Proposal.id == uuid.UUID(body["proposal_id"])))
    ).scalar_one()
    extra = proposal.extra_json or {}
    assert extra.get("creative_proof_slug") == body["creative_proof_slug"]


@pytest.mark.asyncio
async def test_create_proposal_override_package_slug(api_client, db_session, sample_org_data, monkeypatch):
    headers, _, _ = await _register_and_login_proofhook(api_client, db_session, sample_org_data)
    _patch_scanner(monkeypatch)
    submitted = await _submit_test(api_client, db_session)
    report_id = submitted["report_id"]

    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/create-proposal",
        json={"override_package_slug": "ai_search_authority_sprint"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["package_slug"] == "ai_search_authority_sprint"


@pytest.mark.asyncio
async def test_create_proposal_404_for_unknown_report(api_client, db_session, sample_org_data, monkeypatch):
    headers, _, _ = await _register_and_login_proofhook(api_client, db_session, sample_org_data)
    bogus = uuid.uuid4()
    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{bogus}/create-proposal",
        json={},
        headers=headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_proposal_requires_operator_auth(api_client, db_session, sample_org_data):
    # No Authorization header → 401 (or 403)
    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{uuid.uuid4()}/create-proposal",
        json={},
    )
    assert r.status_code in (401, 403)
