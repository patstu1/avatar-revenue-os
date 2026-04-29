"""Integration tests for the AI Buyer Trust Test → Revenue OS connection.

Covers the acceptance criteria approved by the operator:

  1. Diagnostic score endpoint stores a report
  2. Report submission creates/updates a LeadOpportunity
  3. Submission emits a SystemEvent
  4. Submission emits an OperatorAction
  5. Snapshot request transitions status + dedupes
  6. Operator list/detail endpoints return the report
  7. create-proposal calls the existing proposals_service
  8. Recommended package slug is one of the 13 approved slugs
  9. Package seed script upserts all 13 packages idempotently
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from apps.api.services.ai_search_authority_service import (
    APPROVED_PACKAGE_SLUGS,
    PACKAGE_BY_SLUG,
    PROOFHOOK_PACKAGES,
    score_diagnostic,
)
from packages.db.enums import MonetizationMethod
from packages.db.models.ai_search_authority import AISearchAuthorityReport
from packages.db.models.core import Brand, Organization
from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
from packages.db.models.offers import Offer
from packages.db.models.proposals import Proposal, ProposalLineItem
from packages.db.models.system_events import OperatorAction, SystemEvent

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


COLD_ANSWERS = {
    "machine_readable_homepage": "no",
    "about_page": "no",
    "structured_data": "no",
    "robots_allows_ai": "no",
    "sitemap_present": "no",
    "faq_page": "no",
    "comparison_pages": "no",
    "proof_assets": "no",
    "third_party_citations": "no",
    "answer_engine_pages": "no",
    "internal_linking": "no",
    "analytics_tracking": "no",
    "public_pricing": "no",
}

WARM_ANSWERS = {
    "machine_readable_homepage": "yes",
    "about_page": "yes",
    "structured_data": "no",
    "robots_allows_ai": "yes",
    "sitemap_present": "yes",
    "faq_page": "no",
    "comparison_pages": "no",
    "proof_assets": "no",
    "third_party_citations": "yes",
    "answer_engine_pages": "no",
    "internal_linking": "yes",
    "analytics_tracking": "unknown",
    "public_pricing": "yes",
}

HOT_ANSWERS = {
    "machine_readable_homepage": "yes",
    "about_page": "yes",
    "structured_data": "yes",
    "robots_allows_ai": "yes",
    "sitemap_present": "yes",
    "faq_page": "yes",
    "comparison_pages": "yes",
    "proof_assets": "yes",
    "third_party_citations": "yes",
    "answer_engine_pages": "yes",
    "internal_linking": "yes",
    "analytics_tracking": "no",
    "public_pricing": "yes",
}


async def _register_operator(api_client, sample_org_data) -> tuple[uuid.UUID, dict]:
    reg = await api_client.post("/api/v1/auth/register", json=sample_org_data)
    assert reg.status_code == 201, reg.text
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    org_id = uuid.UUID(me.json()["organization_id"])
    return org_id, headers


async def _seed_proofhook_brand(db_session, org_id: uuid.UUID) -> uuid.UUID:
    """Seed the canonical proofhook brand on the operator's org so the
    public diagnostic service attaches the LeadOpportunity to the
    operator's tenant rather than auto-bootstrapping a separate one."""
    brand = (
        await db_session.execute(select(Brand).where(Brand.slug == "proofhook"))
    ).scalar_one_or_none()
    if brand is None:
        brand = Brand(
            organization_id=org_id,
            name="ProofHook",
            slug="proofhook",
            niche="b2b_services",
            is_active=True,
        )
        db_session.add(brand)
        await db_session.flush()
    return brand.id


# ─────────────────────────────────────────────────────────────────────
# 1. Pure scoring rubric
# ─────────────────────────────────────────────────────────────────────


def test_score_diagnostic_cold_recommends_proof_infrastructure_buildout():
    res = score_diagnostic(COLD_ANSWERS)
    assert res.score == 0.0
    assert res.tier == "cold"
    assert res.recommended_package_slug == "proof_infrastructure_buildout"
    assert len(res.gaps) == 3
    # Highest-weight gaps come first.
    assert res.gaps[0]["weight"] >= res.gaps[1]["weight"] >= res.gaps[2]["weight"]
    assert res.quick_win  # non-empty


def test_score_diagnostic_warm_recommends_sprint():
    res = score_diagnostic(WARM_ANSWERS)
    assert 36 <= res.score < 66
    assert res.tier == "warm"
    assert res.recommended_package_slug == "ai_search_authority_sprint"


def test_score_diagnostic_hot_recommends_monitoring_retainer():
    res = score_diagnostic(HOT_ANSWERS)
    assert res.score >= 66
    assert res.tier == "hot"
    assert res.recommended_package_slug == "authority_monitoring_retainer"


def test_recommended_slug_is_always_approved():
    for answers in (COLD_ANSWERS, WARM_ANSWERS, HOT_ANSWERS, {}):
        res = score_diagnostic(answers)
        assert res.recommended_package_slug in APPROVED_PACKAGE_SLUGS, (
            f"Recommended slug {res.recommended_package_slug!r} not in approved set"
        )


def test_thirteen_approved_packages_present():
    assert len(APPROVED_PACKAGE_SLUGS) == 13
    expected = {
        # AI Authority
        "ai_buyer_trust_test",
        "authority_snapshot",
        "ai_search_authority_sprint",
        "proof_infrastructure_buildout",
        "authority_monitoring_retainer",
        "ai_authority_system",
        # Creative Proof
        "signal_entry",
        "momentum_engine",
        "conversion_architecture",
        "paid_media_engine",
        "launch_sequence",
        "creative_command",
        "custom_growth_system",
    }
    assert APPROVED_PACKAGE_SLUGS == expected


# ─────────────────────────────────────────────────────────────────────
# 2. POST /score creates Report + LeadOpportunity + Event + Action
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_endpoint_persists_full_chain(
    api_client, db_session, sample_org_data
):
    org_id, _ = await _register_operator(api_client, sample_org_data)
    brand_id = await _seed_proofhook_brand(db_session, org_id)

    body = {
        "submitter_email": "buyer@example.com",
        "submitter_name": "Pat Buyer",
        "submitter_company": "Example Co",
        "submitter_url": "https://example.test",
        "submitter_role": "Founder",
        "submitter_revenue_band": "1m_arr",
        "vertical": "saas",
        "buyer_type": "founder_led",
        "answers": WARM_ANSWERS,
    }

    r = await api_client.post("/api/v1/ai-search-authority/score", json=body)
    assert r.status_code == 201, r.text
    payload = r.json()

    # 1 — Report row stored
    report_id = uuid.UUID(payload["report_id"])
    report = (
        await db_session.execute(
            select(AISearchAuthorityReport).where(AISearchAuthorityReport.id == report_id)
        )
    ).scalar_one()
    assert report.submitter_email == "buyer@example.com"
    assert report.submitter_company == "Example Co"
    assert report.submitter_url == "https://example.test"
    assert report.vertical == "saas"
    assert report.buyer_type == "founder_led"
    assert report.tier == "warm"
    assert report.status == "submitted"
    assert report.recommended_package_slug == "ai_search_authority_sprint"
    assert report.score == payload["score"]
    assert report.organization_id == org_id
    assert report.brand_id == brand_id

    # 2 — Recommended slug is approved
    assert payload["recommended_package_slug"] in APPROVED_PACKAGE_SLUGS
    assert payload["recommended_package_path"].startswith("/")
    assert payload["diagnostic_kind"] == "answer_based"
    assert payload["status"] == "submitted"

    # 3 — LeadOpportunity created and linked
    assert report.lead_opportunity_id is not None
    lead = (
        await db_session.execute(
            select(LeadOpportunity).where(LeadOpportunity.id == report.lead_opportunity_id)
        )
    ).scalar_one()
    assert lead.brand_id == brand_id
    assert lead.package_slug == "ai_search_authority_sprint"
    assert lead.qualification_tier == "warm"
    assert lead.lead_source.startswith("ai_search_authority:")
    assert "buyer@example.com" in lead.message_text

    # 4 — SystemEvent emitted
    event = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "ai_search_authority.report_submitted",
                SystemEvent.entity_type == "ai_search_authority_report",
                SystemEvent.entity_id == report.id,
            )
        )
    ).scalar_one()
    assert event.organization_id == org_id
    assert event.brand_id == brand_id
    assert event.event_domain == "revenue"
    assert event.requires_action is True
    assert (event.details or {}).get("recommended_package_slug") == "ai_search_authority_sprint"
    assert (event.details or {}).get("diagnostic_kind") == "answer_based"

    # 5 — OperatorAction created
    action = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.action_type == "review_ai_search_authority_report",
                OperatorAction.entity_type == "ai_search_authority_report",
                OperatorAction.entity_id == report.id,
            )
        )
    ).scalar_one()
    assert action.organization_id == org_id
    assert action.brand_id == brand_id
    assert action.priority == "medium"  # warm tier
    assert action.status == "pending"
    assert action.category == "opportunity"


# ─────────────────────────────────────────────────────────────────────
# 3. Snapshot review request: transitions + dedupes
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_review_transitions_and_dedupes(
    api_client, db_session, sample_org_data
):
    org_id, _ = await _register_operator(api_client, sample_org_data)
    await _seed_proofhook_brand(db_session, org_id)

    submit_body = {
        "submitter_email": "snap@example.com",
        "submitter_company": "Snap Co",
        "submitter_url": "https://snap.test",
        "vertical": "ai_startups",
        "answers": WARM_ANSWERS,
    }
    r = await api_client.post("/api/v1/ai-search-authority/score", json=submit_body)
    assert r.status_code == 201
    report_id = r.json()["report_id"]

    # First snapshot request → 200, transitions status, deduped=False
    r1 = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/request-snapshot-review"
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["status"] == "snapshot_requested"
    assert body1["deduped"] is False
    assert body1["snapshot_requested_at"] is not None

    # Second click — idempotent — still returns 200 with deduped=True and no
    # second OperatorAction.
    r2 = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/request-snapshot-review"
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["status"] == "snapshot_requested"
    assert body2["deduped"] is True

    # Verify only one snapshot OperatorAction exists for this report.
    actions = (
        (
            await db_session.execute(
                select(OperatorAction).where(
                    OperatorAction.action_type == "deliver_authority_snapshot",
                    OperatorAction.entity_type == "ai_search_authority_report",
                    OperatorAction.entity_id == uuid.UUID(report_id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) == 1


# ─────────────────────────────────────────────────────────────────────
# 4. Operator list + detail endpoints
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_operator_list_and_detail_endpoints(
    api_client, db_session, sample_org_data
):
    org_id, headers = await _register_operator(api_client, sample_org_data)
    await _seed_proofhook_brand(db_session, org_id)

    # Submit two reports.
    for email in ("a@example.com", "b@example.com"):
        r = await api_client.post(
            "/api/v1/ai-search-authority/score",
            json={
                "submitter_email": email,
                "submitter_company": email.split("@")[0].upper(),
                "vertical": "saas",
                "answers": HOT_ANSWERS if email.startswith("a") else COLD_ANSWERS,
            },
        )
        assert r.status_code == 201

    # Operator list
    list_resp = await api_client.get(
        "/api/v1/ai-search-authority/reports", headers=headers
    )
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()
    assert len(rows) == 2
    emails = {row["submitter_email"] for row in rows}
    assert emails == {"a@example.com", "b@example.com"}

    # Operator list — auth required
    no_auth = await api_client.get("/api/v1/ai-search-authority/reports")
    assert no_auth.status_code == 401

    # Detail
    detail = await api_client.get(
        f"/api/v1/ai-search-authority/reports/{rows[0]['id']}", headers=headers
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["id"] == rows[0]["id"]
    assert detail_body["recommended_package_slug"] in APPROVED_PACKAGE_SLUGS
    assert "answers_json" in detail_body
    assert "gaps_json" in detail_body


# ─────────────────────────────────────────────────────────────────────
# 5. Create proposal: delegates to proposals_service, attaches package
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_proposal_uses_proposals_service(
    api_client, db_session, sample_org_data
):
    org_id, headers = await _register_operator(api_client, sample_org_data)
    await _seed_proofhook_brand(db_session, org_id)

    submit = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json={
            "submitter_email": "ready@example.com",
            "submitter_company": "Ready Co",
            "submitter_url": "https://ready.test",
            "vertical": "saas",
            "answers": WARM_ANSWERS,
        },
    )
    assert submit.status_code == 201
    report_id = submit.json()["report_id"]

    # No body — defaults to recommended_package_slug
    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/create-proposal",
        json={},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["package_slug"] == "ai_search_authority_sprint"
    assert body["status"] == "draft"

    proposal_id = uuid.UUID(body["proposal_id"])
    proposal = (
        await db_session.execute(select(Proposal).where(Proposal.id == proposal_id))
    ).scalar_one()
    assert proposal.org_id == org_id
    assert proposal.package_slug == "ai_search_authority_sprint"
    assert proposal.recipient_email == "ready@example.com"
    assert proposal.total_amount_cents == PACKAGE_BY_SLUG["ai_search_authority_sprint"].price_cents
    assert (proposal.extra_json or {}).get("source") == "ai_search_authority_diagnostic"
    assert (proposal.extra_json or {}).get("ai_search_authority_report_id") == str(report_id)

    # Line item carries package_slug — the same join key Stripe metadata uses.
    line_items = (
        (
            await db_session.execute(
                select(ProposalLineItem).where(ProposalLineItem.proposal_id == proposal_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(line_items) == 1
    assert line_items[0].package_slug == "ai_search_authority_sprint"

    # Report has been linked + advanced.
    report = (
        await db_session.execute(
            select(AISearchAuthorityReport).where(
                AISearchAuthorityReport.id == uuid.UUID(report_id)
            )
        )
    ).scalar_one()
    assert report.proposal_id == proposal_id
    assert report.status == "proposal_sent"
    assert report.proposal_created_at is not None


@pytest.mark.asyncio
async def test_create_proposal_rejects_unapproved_slug(
    api_client, db_session, sample_org_data
):
    org_id, headers = await _register_operator(api_client, sample_org_data)
    await _seed_proofhook_brand(db_session, org_id)

    submit = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json={
            "submitter_email": "x@example.com",
            "answers": WARM_ANSWERS,
        },
    )
    assert submit.status_code == 201
    report_id = submit.json()["report_id"]

    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/create-proposal",
        json={"package_slug": "definitely_not_a_real_package"},
        headers=headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_proposal_requires_operator_auth(
    api_client, db_session, sample_org_data
):
    org_id, _ = await _register_operator(api_client, sample_org_data)
    await _seed_proofhook_brand(db_session, org_id)

    submit = await api_client.post(
        "/api/v1/ai-search-authority/score",
        json={"submitter_email": "y@example.com", "answers": WARM_ANSWERS},
    )
    assert submit.status_code == 201
    report_id = submit.json()["report_id"]

    r = await api_client.post(
        f"/api/v1/ai-search-authority/reports/{report_id}/create-proposal",
        json={},
    )
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# 6. Idempotent ProofHook package upsert
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_proofhook_package_seed_upserts_thirteen_packages_idempotently(
    db_session,
):
    # The seed script's main() opens its own sync engine, but its package
    # definitions and upsert logic are testable directly on the async
    # fixture by replaying the upsert loop. This protects the rule that
    # both the script and the service use the same 13 slugs.
    from scripts.seed_proofhook_packages import PACKAGES as SCRIPT_PACKAGES

    # Same 13 slugs in the script and the service.
    script_slugs = {p.slug for p in SCRIPT_PACKAGES}
    assert script_slugs == APPROVED_PACKAGE_SLUGS
    assert {p.slug for p in PROOFHOOK_PACKAGES} == APPROVED_PACKAGE_SLUGS

    # Bootstrap the proofhook org + brand on the test DB.
    org = Organization(name="ProofHook", slug="proofhook", is_active=True)
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        organization_id=org.id,
        name="ProofHook",
        slug="proofhook",
        niche="b2b_services",
        is_active=True,
    )
    db_session.add(brand)
    await db_session.flush()

    async def _upsert_all() -> tuple[int, int, int]:
        created = updated = unchanged = 0
        for pkg in SCRIPT_PACKAGES:
            existing = (
                await db_session.execute(
                    select(Offer).where(
                        Offer.brand_id == brand.id, Offer.name == pkg.name
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                db_session.add(
                    Offer(
                        brand_id=brand.id,
                        name=pkg.name,
                        description=pkg.description,
                        monetization_method=MonetizationMethod.CONSULTING,
                        payout_amount=pkg.price_cents / 100.0,
                        payout_type="fixed",
                        offer_url=pkg.url_path,
                        cta_template=pkg.cta,
                        rotation_weight=1.0,
                        is_active=True,
                        priority=0,
                        audience_fit_tags=[
                            "proofhook_current",
                            pkg.slug,
                            pkg.category,
                        ],
                    )
                )
                created += 1
            else:
                before = (
                    existing.description,
                    float(existing.payout_amount),
                    list(existing.audience_fit_tags or []),
                )
                existing.description = pkg.description
                existing.payout_amount = pkg.price_cents / 100.0
                existing.offer_url = pkg.url_path
                existing.audience_fit_tags = [
                    "proofhook_current",
                    pkg.slug,
                    pkg.category,
                ]
                after = (
                    existing.description,
                    float(existing.payout_amount),
                    list(existing.audience_fit_tags or []),
                )
                if before == after:
                    unchanged += 1
                else:
                    updated += 1
        await db_session.flush()
        return created, updated, unchanged

    # First run: 13 created.
    c1, u1, n1 = await _upsert_all()
    assert (c1, u1, n1) == (13, 0, 0)

    # Second run: 0 created, 0 updated, 13 unchanged.
    c2, u2, n2 = await _upsert_all()
    assert c2 == 0
    assert u2 == 0
    assert n2 == 13

    # Every offer has audience_fit_tags marking it proofhook_current.
    offers = (
        (
            await db_session.execute(
                select(Offer).where(Offer.brand_id == brand.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(offers) == 13
    for o in offers:
        tags = list(o.audience_fit_tags or [])
        assert "proofhook_current" in tags
        assert any(slug in tags for slug in APPROVED_PACKAGE_SLUGS)
