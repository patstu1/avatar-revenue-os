"""Integration tests for the AI Buyer Trust Test full flow.

Mocks the website scanner with a deterministic in-memory ScanResult so we
exercise the orchestrator + DB persistence + LeadOpportunity upsert +
OperatorAction emission + SystemEvent emission without hitting the network.

Re-runs `tests/integration/test_proofhook_public_checkout.py` is NOT done
here — that suite is gated by the same conftest fixture and is asserted
unbroken by the final implementation report.
"""

from __future__ import annotations

import importlib
import uuid

import packages.db.models  # noqa: F401 — registers all models
import packages.db.models.expansion_pack2_phase_a  # noqa: F401
import packages.db.models.system_events  # noqa: F401
import packages.db.models.proposals  # noqa: F401
import packages.db.models.clients  # noqa: F401
import packages.db.models.fulfillment  # noqa: F401
import packages.db.models.live_execution_phase2  # noqa: F401
import packages.db.models.delivery  # noqa: F401
import packages.db.models.gm_control  # noqa: F401
import packages.db.models.authority_score_reports  # noqa: F401

import pytest
from sqlalchemy import select

from packages.db.models.authority_score_reports import AuthorityScoreReport
from packages.db.models.core import Brand, Organization
from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
from packages.db.models.system_events import OperatorAction, SystemEvent

PUBLIC_HTML = """
<!doctype html>
<html><head>
  <title>Acme — fraud detection for B2B SaaS</title>
  <meta name="description" content="We help B2B SaaS finance teams reduce fraud loss without burning conversions.">
  <script type="application/ld+json">{"@type":"Organization","name":"Acme","url":"https://acme.io","sameAs":["https://x.com/acmehq"]}</script>
  <script type="application/ld+json">{"@type":"FAQPage"}</script>
  <script type="application/ld+json">{"@type":"Service","name":"Fraud detection"}</script>
</head><body>
  <h1>Stop payment fraud before checkout.</h1>
  <h2>How Acme works</h2>
  <h2>Pricing</h2>
  <p>For B2B SaaS finance teams. Unlike legacy fraud tools. 1234 Market Street, Suite 200. (415) 555-0100. hello@acme.io.</p>
  <a href="/about">About</a>
  <a href="/pricing">Pricing</a>
  <a href="/faq">FAQ</a>
  <a href="/case-studies">Case Studies</a>
  <a href="/compare/competitor">Acme vs Competitor</a>
  <a href="/contact">Contact</a>
</body></html>
""".encode("utf-8")

ABOUT_HTML = b"<html><body><h1>About</h1><p>For B2B SaaS finance teams.</p></body></html>"
PRICING_HTML = b"<html><body><h1>Pricing</h1><p>Starts at $499/mo.</p></body></html>"
FAQ_HTML = (
    b"<html><body><h1>FAQ</h1>"
    b"<h2>What does Acme do?</h2><h2>How much does Acme cost?</h2>"
    b"<h2>How long is setup?</h2><h2>Do you replace Sift?</h2>"
    b"<h2>Where is data stored?</h2><h2>What support is included?</h2>"
    b"<h2>Do you integrate with Stripe?</h2></body></html>"
)
CASE_HTML = b"<html><body><h1>Case studies</h1><p>Testimonial from Foo: case study with named clients.</p></body></html>"
COMPARE_HTML = "<html><body><h1>Acme vs Competitor</h1><p>Acme vs Competitor — pricing.</p></body></html>".encode("utf-8")
CONTACT_HTML = b"<html><body><h1>Contact</h1><p>1234 Market.</p></body></html>"


PAGE_RESPONSES: dict[str, bytes] = {
    "https://acme.io": PUBLIC_HTML,
    "https://acme.io/about": ABOUT_HTML,
    "https://acme.io/pricing": PRICING_HTML,
    "https://acme.io/faq": FAQ_HTML,
    "https://acme.io/case-studies": CASE_HTML,
    "https://acme.io/compare/competitor": COMPARE_HTML,
    "https://acme.io/contact": CONTACT_HTML,
}


async def _seed_proofhook_org_and_brand(db_session) -> tuple[uuid.UUID, uuid.UUID]:
    org = Organization(name="ProofHook", slug="proofhook", is_active=True)
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        organization_id=org.id,
        name="ProofHook",
        slug="proofhook",
        niche="b2b",
        is_active=True,
    )
    db_session.add(brand)
    await db_session.flush()
    await db_session.commit()
    return org.id, brand.id


def _patch_scanner(monkeypatch, page_map: dict[str, bytes] | None = None, fail_homepage: bool = False):
    """Replace the scanner's `scan_website` with a deterministic in-memory
    version that calls the same parse + signal-shape helpers."""
    from apps.api.services import website_scanner as ws

    page_map = page_map if page_map is not None else PAGE_RESPONSES

    async def fake_scan(homepage_url: str):
        result = ws.ScanResult(homepage_url=homepage_url)
        # Homepage
        if fail_homepage:
            page = ws.FetchedPage(
                url=homepage_url, status_code=500, fetch_error="http_500", content_type=None
            )
            result.pages.append(page)
            result.homepage_failed = True
            return result
        body = page_map.get(homepage_url)
        if body is None:
            result.homepage_failed = True
            result.pages.append(
                ws.FetchedPage(url=homepage_url, status_code=404, fetch_error="http_404")
            )
            return result
        page = ws.parse_html_into_page(body, homepage_url)
        result.pages.append(page)
        # Subpages: fetch every URL in the page_map that isn't the homepage.
        for url, sub_body in page_map.items():
            if url == homepage_url:
                continue
            sub = ws.parse_html_into_page(sub_body, url)
            result.pages.append(sub)
        # robots/sitemap defaults
        result.robots_txt_present = True
        result.sitemap_present = True
        result.sitemap_url_count = 10
        return result

    monkeypatch.setattr(ws, "scan_website", fake_scan)
    # The orchestrator imports scan_website by name from the module.
    monkeypatch.setattr(
        "apps.api.services.ai_buyer_trust_service.scan_website", fake_scan
    )


@pytest.mark.asyncio
async def test_full_flow_creates_report_lead_action_event(api_client, db_session, monkeypatch):
    org_id, brand_id = await _seed_proofhook_org_and_brand(db_session)
    _patch_scanner(monkeypatch)

    payload = {
        "website_url": "https://acme.io",
        "company_name": "Acme",
        "industry": "B2B SaaS",
        "contact_email": "pat@acme.io",
        "competitor_url": "https://competitor.io",
        "city_or_market": "San Francisco",
    }
    r = await api_client.post("/api/v1/ai-search-authority/score", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()

    # Public envelope shape
    assert body["status"] == "scored"
    assert isinstance(body["total_score"], int)
    assert body["total_score"] > 0
    assert body["score_label"] in {"weak", "developing", "strong", "authority_ready", "not_ready"}
    assert body["confidence_label"] in {"low", "medium", "high"}
    assert body["recommended_package"]["primary_slug"] is not None
    assert "creative_proof_slug" in body["recommended_package"]
    assert "Get My Full Authority Snapshot" == body["cta"]["label"]
    assert "report_id" in body
    # Buyer questions preview present
    assert isinstance(body["buyer_questions_preview"], list)
    assert len(body["buyer_questions_preview"]) >= 1
    assert "Acme" in body["buyer_questions_preview"][0]["question"]
    # Platform hint copy present
    assert "first_snapshot" in body["platform_hint"]
    # Disclaimer is affirmative — describes what the score is based on +
    # what review happens. No defensive "we do not / no rankings" copy.
    disc = body["disclaimer"].lower()
    assert "public website signals" in disc
    assert "operator-reviewed" in disc
    assert "we do not" not in disc
    assert "no ranking guarantees" not in disc
    assert "no ai-placement promises" not in disc

    # Report row persisted with platform-ready fields
    report = (
        await db_session.execute(
            select(AuthorityScoreReport).where(
                AuthorityScoreReport.organization_id == org_id,
                AuthorityScoreReport.contact_email == "pat@acme.io",
            )
        )
    ).scalar_one()
    assert report.report_status == "scored"
    assert report.total_score == body["total_score"]
    assert report.authority_score == body["total_score"]
    assert isinstance(report.dimension_scores, dict) and len(report.dimension_scores) == 8
    assert isinstance(report.evidence, dict) and len(report.evidence) == 8
    assert isinstance(report.authority_graph, dict) and "entity" in report.authority_graph
    assert isinstance(report.buyer_questions, list) and len(report.buyer_questions) >= 5
    assert isinstance(report.recommended_pages, list)
    assert isinstance(report.recommended_schema, list)
    assert isinstance(report.recommended_proof_assets, list)
    assert isinstance(report.recommended_comparison_surfaces, list)
    assert isinstance(report.monitoring_recommendation, str)
    assert report.formula_version == "v1"
    assert report.report_version == "v1"
    assert report.scan_version == "v1"

    # LeadOpportunity created
    lead = (
        await db_session.execute(
            select(LeadOpportunity).where(LeadOpportunity.brand_id == brand_id)
        )
    ).scalar_one()
    assert lead.lead_source == "ai_buyer_trust_test"
    assert lead.package_slug == report.recommended_package_slug
    assert "pat@acme.io" in (lead.message_text or "")

    # OperatorAction emitted
    action = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.organization_id == org_id,
                OperatorAction.action_type == "review_buyer_trust_lead",
            )
        )
    ).scalar_one()
    assert action.entity_type == "authority_score_report"
    assert action.entity_id == report.id

    # SystemEvent emitted
    ev = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "ai_buyer_trust.test_completed",
                SystemEvent.event_domain == "growth",
            )
        )
    ).scalar_one()
    assert (ev.details or {}).get("report_id") == str(report.id)


@pytest.mark.asyncio
async def test_dedup_returns_prior_report_within_window(api_client, db_session, monkeypatch):
    await _seed_proofhook_org_and_brand(db_session)
    _patch_scanner(monkeypatch)
    payload = {
        "website_url": "https://acme.io",
        "company_name": "Acme",
        "industry": "B2B SaaS",
        "contact_email": "pat@acme.io",
    }
    r1 = await api_client.post("/api/v1/ai-search-authority/score", json=payload)
    assert r1.status_code == 200
    r2 = await api_client.post("/api/v1/ai-search-authority/score", json=payload)
    assert r2.status_code == 200
    assert r2.json().get("deduplicated") is True
    assert r2.json()["report_id"] == r1.json()["report_id"]


@pytest.mark.asyncio
async def test_invalid_url_returns_400(api_client, db_session, monkeypatch):
    await _seed_proofhook_org_and_brand(db_session)
    _patch_scanner(monkeypatch)
    payload = {
        "website_url": "http://localhost",
        "company_name": "Acme",
        "industry": "X",
        "contact_email": "pat@acme.io",
    }
    r = await api_client.post("/api/v1/ai-search-authority/score", json=payload)
    assert r.status_code == 400
    body = r.json()
    assert body["detail"]["field"] == "website_url"


@pytest.mark.asyncio
async def test_throwaway_email_returns_400(api_client, db_session, monkeypatch):
    await _seed_proofhook_org_and_brand(db_session)
    _patch_scanner(monkeypatch)
    payload = {
        "website_url": "https://acme.io",
        "company_name": "Acme",
        "industry": "X",
        "contact_email": "test@example.com",
    }
    r = await api_client.post("/api/v1/ai-search-authority/score", json=payload)
    assert r.status_code == 400
    body = r.json()
    assert body["detail"]["field"] == "contact_email"


@pytest.mark.asyncio
async def test_failed_homepage_returns_friendly_envelope(api_client, db_session, monkeypatch):
    org_id, _ = await _seed_proofhook_org_and_brand(db_session)
    _patch_scanner(monkeypatch, fail_homepage=True)
    payload = {
        "website_url": "https://acme.io",
        "company_name": "Acme",
        "industry": "X",
        "contact_email": "pat@acme.io",
    }
    r = await api_client.post("/api/v1/ai-search-authority/score", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert body["score_label"] == "not_assessed"
    assert body["recommended_package"]["primary_slug"] is None
    # Report still persisted with failed status
    rep = (
        await db_session.execute(
            select(AuthorityScoreReport).where(AuthorityScoreReport.organization_id == org_id)
        )
    ).scalar_one()
    assert rep.report_status == "failed"
    assert rep.fetch_error
