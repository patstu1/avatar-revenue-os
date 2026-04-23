"""Integration tests — last-mile closure: affiliate sync, landing page publish,
recovery auto-execution, permission enforcement, disclosure injection."""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from packages.db.models.core import Organization, User, Brand
from packages.db.models.affiliate_intel import AffiliateNetworkAccount, AffiliateOffer, AffiliateLink
from packages.db.models.landing_pages import LandingPage, LandingPageQualityReport, LandingPagePublishRecord
from packages.db.models.recovery_engine import RecoveryIncidentV2, RollbackAction, RerouteAction, ThrottlingAction, RecoveryOutcome
from packages.db.models.operator_permission_matrix import OperatorPermissionMatrix
from packages.db.models.content import ContentItem
from packages.db.enums import Platform, ContentType

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def setup_org(db_session):
    org = Organization(name="LastMile Org", slug=f"lm-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()
    brand = Brand(organization_id=org.id, name="LM Brand", slug=f"lm-brand-{uuid.uuid4().hex[:6]}", niche="tech")
    db_session.add(brand)
    await db_session.flush()
    return org, brand


# ── 1. Affiliate Sync Path ──

async def test_affiliate_sync_no_networks(db_session, setup_org):
    from apps.api.services.affiliate_sync_service import sync_network_data
    _, brand = setup_org
    result = await sync_network_data(db_session, brand.id)
    assert result["networks_checked"] == 0
    assert result["status"] == "completed"


async def test_affiliate_sync_with_network(db_session, setup_org):
    from apps.api.services.affiliate_sync_service import sync_network_data
    _, brand = setup_org
    net = AffiliateNetworkAccount(brand_id=brand.id, network_name="Impact", is_active=True)
    db_session.add(net)
    await db_session.flush()
    result = await sync_network_data(db_session, brand.id)
    assert result["networks_checked"] == 1


# ── 2. Landing Page Publish Path ──

async def test_landing_page_publish_success(db_session, setup_org):
    from apps.api.services.landing_page_service import publish_page
    _, brand = setup_org
    page = LandingPage(brand_id=brand.id, page_type="offer_page", headline="Test Offer", status="draft", publish_status="unpublished", truth_label="recommendation_only")
    db_session.add(page)
    await db_session.flush()

    result = await publish_page(db_session, page.id, "manual", "https://example.com/offer")
    assert result["success"]
    assert result["truth_label"] == "published"
    assert result["destination_url"] == "https://example.com/offer"
    assert page.publish_status == "published"
    assert page.truth_label == "published"


async def test_landing_page_publish_requires_url(db_session, setup_org):
    from apps.api.services.landing_page_service import publish_page
    _, brand = setup_org
    page = LandingPage(brand_id=brand.id, page_type="offer_page", headline="Test", status="draft", publish_status="unpublished", truth_label="recommendation_only")
    db_session.add(page)
    await db_session.flush()

    result = await publish_page(db_session, page.id, "manual", "")
    assert not result["success"]
    assert "destination_url" in result["reason"]


async def test_landing_page_publish_blocked_by_quality(db_session, setup_org):
    from apps.api.services.landing_page_service import publish_page
    _, brand = setup_org
    page = LandingPage(brand_id=brand.id, page_type="offer_page", headline="Bad Page", status="draft")
    db_session.add(page)
    await db_session.flush()
    qr = LandingPageQualityReport(page_id=page.id, brand_id=brand.id, total_score=0.2, verdict="fail")
    db_session.add(qr)
    await db_session.flush()

    result = await publish_page(db_session, page.id, "manual", "https://example.com/bad")
    assert not result["success"]
    assert "Quality gate failed" in result["reason"]


async def test_landing_page_publish_record_created(db_session, setup_org):
    from apps.api.services.landing_page_service import publish_page
    from sqlalchemy import select
    _, brand = setup_org
    page = LandingPage(brand_id=brand.id, page_type="offer_page", headline="Record Test", status="draft", publish_status="unpublished", truth_label="recommendation_only")
    db_session.add(page)
    await db_session.flush()
    await publish_page(db_session, page.id, "manual", "https://example.com/record")
    records = list((await db_session.execute(select(LandingPagePublishRecord).where(LandingPagePublishRecord.page_id == page.id))).scalars().all())
    assert len(records) == 1
    assert records[0].published_url == "https://example.com/record"
    assert records[0].truth_label == "published"


# ── 3. Recovery Auto-Execution ──

async def test_recovery_auto_execute_with_permission(db_session, setup_org):
    from apps.api.services.recovery_engine_service import execute_pending_recovery_actions
    org, _ = setup_org
    inc = RecoveryIncidentV2(organization_id=org.id, incident_type="provider_failure", severity="high", affected_scope="provider", detail="test provider outage", recovery_status="auto_recovering")
    db_session.add(inc)
    await db_session.flush()
    rb = RollbackAction(incident_id=inc.id, rollback_type="rollback", rollback_target="provider_x", execution_status="pending")
    db_session.add(rb)
    await db_session.flush()

    result = await execute_pending_recovery_actions(db_session, org.id)
    assert result["rollbacks"] >= 1
    assert rb.execution_status == "executed"


async def test_recovery_auto_execute_skips_not_auto_recovering(db_session, setup_org):
    from apps.api.services.recovery_engine_service import execute_pending_recovery_actions
    org, _ = setup_org
    inc = RecoveryIncidentV2(organization_id=org.id, incident_type="provider_failure", severity="high", affected_scope="provider", detail="test pending incident", recovery_status="pending_review")
    db_session.add(inc)
    await db_session.flush()
    rb = RollbackAction(incident_id=inc.id, rollback_type="rollback", rollback_target="provider_x", execution_status="pending")
    db_session.add(rb)
    await db_session.flush()

    result = await execute_pending_recovery_actions(db_session, org.id)
    assert result["rollbacks"] == 0
    assert rb.execution_status == "pending"


# ── 4. Permission Enforcement ──

async def test_permission_enforcement_allows_autonomous(db_session, setup_org):
    from apps.api.services.permission_enforcement import enforce_permission
    org, _ = setup_org
    result = await enforce_permission(db_session, org.id, "generate_content")
    assert result["allowed"]


async def test_permission_enforcement_blocks_manual_only(db_session, setup_org):
    from apps.api.services.permission_enforcement import enforce_permission, PermissionDenied
    org, _ = setup_org
    with pytest.raises(PermissionDenied) as exc_info:
        await enforce_permission(db_session, org.id, "governance_override")
    assert "manual" in str(exc_info.value).lower()


async def test_permission_enforcement_blocks_guarded(db_session, setup_org):
    from apps.api.services.permission_enforcement import enforce_permission, PermissionDenied
    org, _ = setup_org
    with pytest.raises(PermissionDenied):
        await enforce_permission(db_session, org.id, "launch_campaign")


async def test_permission_matrix_overrides_default(db_session, setup_org):
    from apps.api.services.permission_enforcement import enforce_permission, PermissionDenied
    org, _ = setup_org
    db_session.add(OperatorPermissionMatrix(
        organization_id=org.id, action_class="campaign_launch",
        autonomy_mode="manual_only", approval_role="org_admin",
        override_allowed=False, override_role="super_admin",
    ))
    await db_session.flush()
    with pytest.raises(PermissionDenied) as exc_info:
        await enforce_permission(db_session, org.id, "launch_campaign")
    assert "manual" in str(exc_info.value).lower()


# ── 5. Disclosure Injection (DB-backed) ──

async def test_disclosure_injection_db(db_session, setup_org):
    from apps.api.services.disclosure_injection_service import check_and_inject_disclosure
    from packages.db.models.accounts import CreatorAccount
    _, brand = setup_org
    acct = CreatorAccount(brand_id=brand.id, platform=Platform.YOUTUBE, platform_username="@test_disc")
    db_session.add(acct)
    await db_session.flush()
    ci = ContentItem(brand_id=brand.id, creator_account_id=acct.id, platform=Platform.YOUTUBE, content_type=ContentType.SHORT_VIDEO, title="Test Review", description="Great product here.", status="approved")
    db_session.add(ci)
    await db_session.flush()

    result = await check_and_inject_disclosure(db_session, ci.id)
    assert not result["injected"] or result["reason"] == "no_disclosure_required"


async def test_disclosure_injection_not_found(db_session, setup_org):
    from apps.api.services.disclosure_injection_service import check_and_inject_disclosure
    result = await check_and_inject_disclosure(db_session, uuid.uuid4())
    assert not result["injected"]
    assert result["reason"] == "content_not_found"


# ── 6. Buffer Credential Naming ──

async def test_buffer_env_var_readiness():
    from packages.scoring.autonomous_readiness_engine import evaluate_autonomous_readiness
    import os
    old = os.environ.get("BUFFER_API_KEY")
    os.environ["BUFFER_API_KEY"] = ""
    r = evaluate_autonomous_readiness()
    assert "BUFFER_API_KEY" in str(r)
    if old:
        os.environ["BUFFER_API_KEY"] = old
    elif "BUFFER_API_KEY" in os.environ:
        del os.environ["BUFFER_API_KEY"]
