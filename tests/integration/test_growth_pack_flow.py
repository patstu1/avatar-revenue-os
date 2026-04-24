"""Integration tests: Growth Pack + Growth Commander against persisted Postgres state."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from apps.api.services import growth_pack_service as gps
from packages.db.enums import ConfidenceLevel, Platform, RecommendedAction
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.offers import SponsorProfile
from packages.db.models.portfolio import RevenueLeakReport, ScaleRecommendation
from packages.db.models.scale_alerts import LaunchCandidate, LaunchReadinessReport


async def _register_brand_offers(api_client, sample_org_data, *, niche: str = "finance", n_offers: int = 2):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "GP Brand", "slug": f"gp-{uuid.uuid4().hex[:8]}", "niche": niche},
        headers=headers,
    )
    bid = brand.json()["id"]
    for i in range(n_offers):
        await api_client.post(
            "/api/v1/offers/",
            json={
                "brand_id": bid,
                "name": f"Offer {i}",
                "monetization_method": "affiliate",
                "epc": 2.0 + i,
                "conversion_rate": 0.03,
            },
            headers=headers,
        )
    return headers, bid


def _seed_creator_accounts(db_session, brand_id: uuid.UUID, rows: list[tuple[str, str, str]]) -> None:
    """Persist creator accounts: (platform_username, platform_key, niche_focus). platform_key: youtube | instagram."""
    plat_map = {
        "youtube": Platform.YOUTUBE,
        "instagram": Platform.INSTAGRAM,
    }
    for username, plat_key, niche in rows:
        db_session.add(
            CreatorAccount(
                brand_id=brand_id,
                platform=plat_map[plat_key],
                platform_username=username,
                niche_focus=niche,
                posting_capacity_per_day=2,
            )
        )


def _scale_rec(
    brand_id: uuid.UUID,
    *,
    rec_key: str = "add_platform_specific_account",
    inc_new: float = 800.0,
    inc_vol: float = 200.0,
    rec_n: int = 3,
    bna: dict | None = None,
) -> ScaleRecommendation:
    return ScaleRecommendation(
        brand_id=brand_id,
        creator_account_id=None,
        recommended_action=RecommendedAction.EXPERIMENT,
        recommendation_key=rec_key,
        incremental_profit_new_account=inc_new,
        incremental_profit_existing_push=inc_vol,
        comparison_ratio=inc_new / max(1e-6, inc_vol),
        scale_readiness_score=72.0,
        cannibalization_risk_score=0.2,
        audience_segment_separation=0.6,
        expansion_confidence=0.82,
        recommended_account_count=rec_n,
        weekly_action_plan={},
        best_next_account=bna
        or {"platform_suggestion": "instagram", "niche_suggestion": "signals", "rationale": "test"},
        score_components={},
        penalties={},
        confidence=ConfidenceLevel.HIGH,
        explanation="integration seed",
        is_actioned=False,
    )


@pytest.mark.asyncio
async def test_strong_platform_opportunity_exact_launch_blueprint(api_client, db_session, sample_org_data):
    """High-confidence Instagram candidate + favorable scale → persisted blueprint matches platform OS."""
    _, bid = await _register_brand_offers(api_client, sample_org_data, n_offers=2)
    brand_uuid = uuid.UUID(bid)
    brand = (await db_session.execute(select(Brand).where(Brand.id == brand_uuid))).scalar_one()
    for sn in ("Acme Sponsors", "Beta Media"):
        db_session.add(SponsorProfile(brand_id=brand_uuid, sponsor_name=sn, is_active=True))
    db_session.add(_scale_rec(brand_uuid, inc_new=900, inc_vol=100))
    db_session.add(
        LaunchReadinessReport(
            brand_id=brand_uuid,
            launch_readiness_score=78.0,
            recommended_action="launch",
            is_active=True,
        )
    )
    db_session.add(
        LaunchCandidate(
            brand_id=brand_uuid,
            candidate_type="platform_expansion",
            primary_platform="instagram",
            niche=brand.niche or "finance",
            sub_niche="signals",
            expected_monthly_revenue_min=100,
            expected_monthly_revenue_max=2400,
            expected_launch_cost=200,
            cannibalization_risk=0.15,
            audience_separation_score=0.72,
            confidence=0.91,
            urgency=80.0,
            supporting_reasons=["strong_platform_fit"],
            launch_blockers=[],
            is_active=True,
        )
    )
    await db_session.commit()

    await gps.recompute_account_blueprints(db_session, brand_uuid)
    rows = await gps.list_account_blueprints(db_session, brand_uuid)
    assert len(rows) >= 1
    bp = rows[0]
    assert bp["platform"] == "instagram"
    assert bp["persona_strategy_json"].get("platform_os", {}).get("recommended_roles")
    assert "reels_satellite" in str(bp["persona_strategy_json"].get("platform_os", {}).get("recommended_roles", []))


@pytest.mark.asyncio
async def test_funnel_weakness_blocks_expansion_blocker_command(api_client, db_session, sample_org_data):
    """Low launch readiness → fix_funnel_first style command and funnel blocker; expansion deferred."""
    _, bid = await _register_brand_offers(api_client, sample_org_data, n_offers=2)
    brand_uuid = uuid.UUID(bid)
    brand = (await db_session.execute(select(Brand).where(Brand.id == brand_uuid))).scalar_one()
    db_session.add(_scale_rec(brand_uuid, inc_new=500, inc_vol=100))
    db_session.add(
        LaunchReadinessReport(
            brand_id=brand_uuid,
            launch_readiness_score=38.0,
            recommended_action="fix_funnel",
            is_active=True,
        )
    )
    db_session.add(
        LaunchCandidate(
            brand_id=brand_uuid,
            candidate_type="growth",
            primary_platform="youtube",
            niche=brand.niche or "finance",
            cannibalization_risk=0.2,
            audience_separation_score=0.6,
            confidence=0.7,
            urgency=50.0,
            supporting_reasons=["test"],
            launch_blockers=[],
            is_active=True,
        )
    )
    await db_session.commit()

    ctx = await gps._load_generation_inputs(db_session, brand_uuid)  # noqa: SLF001
    types = [c["command_type"] for c in ctx["commands"]]
    assert "fix_funnel_first" in types
    assert not any(c.get("command_type") == "launch_account" for c in ctx["commands"])
    assert any((c.get("evidence") or {}).get("gating_primary") == "funnel" for c in ctx["commands"])
    await gps.recompute_growth_blockers_pack(db_session, brand_uuid)
    blockers = await gps.list_growth_blockers_pack(db_session, brand_uuid)
    assert any(b["blocker_type"] in ("funnel_readiness", "gatekeeper_funnel") for b in blockers)


@pytest.mark.asyncio
async def test_cross_account_overlap_suppresses_launch(api_client, db_session, sample_org_data):
    """Two accounts same platform + overlapping niche → high cannibalization gate defers launch."""
    _, bid = await _register_brand_offers(api_client, sample_org_data, niche="personal finance", n_offers=2)
    brand_uuid = uuid.UUID(bid)
    _seed_creator_accounts(
        db_session,
        brand_uuid,
        [
            ("ov_a", "youtube", "personal finance investing"),
            ("ov_b", "youtube", "personal finance investing"),
        ],
    )
    db_session.add(_scale_rec(brand_uuid, inc_new=600, inc_vol=150))
    db_session.add(
        LaunchReadinessReport(
            brand_id=brand_uuid,
            launch_readiness_score=72.0,
            recommended_action="launch",
            is_active=True,
        )
    )
    db_session.add(
        LaunchCandidate(
            brand_id=brand_uuid,
            candidate_type="growth",
            primary_platform="youtube",
            niche="personal finance investing",
            cannibalization_risk=0.25,
            audience_separation_score=0.5,
            confidence=0.75,
            urgency=60.0,
            supporting_reasons=["overlap_scenario"],
            launch_blockers=[],
            is_active=True,
        )
    )
    await db_session.commit()

    ctx = await gps._load_generation_inputs(db_session, brand_uuid)  # noqa: SLF001
    assert any(
        (c.get("evidence") or {}).get("gating_primary") == "overlap"
        or "DEFERRED EXPANSION (overlap)" in c.get("title", "")
        for c in ctx["commands"]
    )


@pytest.mark.asyncio
async def test_capital_constraint_changes_deployment_plan(api_client, db_session, sample_org_data):
    """High leak load marks capital plan constrained (higher holdback)."""
    _, bid = await _register_brand_offers(api_client, sample_org_data, n_offers=2)
    brand_uuid = uuid.UUID(bid)
    db_session.add(_scale_rec(brand_uuid, inc_new=400, inc_vol=200))
    db_session.add(
        LaunchReadinessReport(
            brand_id=brand_uuid,
            launch_readiness_score=70.0,
            recommended_action="launch",
            is_active=True,
        )
    )
    for _ in range(7):
        db_session.add(
            RevenueLeakReport(
                brand_id=brand_uuid,
                leak_type="conversion",
                affected_entity_type="funnel",
                estimated_leaked_revenue=50.0,
                is_resolved=False,
            )
        )
    await db_session.commit()

    await gps.recompute_capital_deployment(db_session, brand_uuid)
    constrained_rows = await gps.list_capital_deployment(db_session, brand_uuid)
    assert constrained_rows[0]["explanation_json"].get("capital_constrained") is True
    hold_constrained = constrained_rows[0]["holdback_budget"]

    leaks = (
        (await db_session.execute(select(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand_uuid)))
        .scalars()
        .all()
    )
    for L in leaks:
        L.is_resolved = True
    await db_session.commit()

    await gps.recompute_capital_deployment(db_session, brand_uuid)
    loose_rows = await gps.list_capital_deployment(db_session, brand_uuid)
    assert loose_rows[0]["explanation_json"].get("capital_constrained") is False
    assert hold_constrained > loose_rows[0]["holdback_budget"]


@pytest.mark.asyncio
async def test_output_governor_throttles_saturated_platform(api_client, db_session, sample_org_data):
    """Three accounts on one platform → portfolio output throttle JSON for that platform."""
    _, bid = await _register_brand_offers(api_client, sample_org_data, n_offers=2)
    brand_uuid = uuid.UUID(bid)
    _seed_creator_accounts(
        db_session,
        brand_uuid,
        [
            ("sat_0", "instagram", "finance"),
            ("sat_1", "instagram", "finance"),
            ("sat_2", "instagram", "finance"),
        ],
    )
    await db_session.commit()

    await gps.recompute_portfolio_output(db_session, brand_uuid)
    out = await gps.list_portfolio_output(db_session, brand_uuid)
    throttle = out[0]["throttle_recommendation_json"]
    assert "instagram" in throttle
    assert "throttle" in throttle["instagram"]["action"].lower() or "throttle" in throttle["instagram"].get(
        "reason", ""
    )


@pytest.mark.asyncio
async def test_seven_platform_allocation_rows_with_os_rationale(api_client, db_session, sample_org_data):
    """All seven platforms (TikTok, Instagram, YouTube, X, Reddit, LinkedIn, Facebook) receive allocation rows with platform_os rationale."""
    _, bid = await _register_brand_offers(api_client, sample_org_data, n_offers=2)
    brand_uuid = uuid.UUID(bid)
    db_session.add(_scale_rec(brand_uuid, rec_n=4, inc_new=300, inc_vol=100))
    await db_session.commit()

    await gps.recompute_platform_allocation(db_session, brand_uuid)
    rows = await gps.list_platform_allocation(db_session, brand_uuid)
    platforms = {r["platform"] for r in rows}
    expected = {"tiktok", "instagram", "youtube", "twitter", "reddit", "linkedin", "facebook"}
    assert platforms == expected
    for r in rows:
        osr = (r.get("rationale_json") or {}).get("platform_os") or {}
        assert osr.get("recommended_roles"), f"missing OS roles for {r['platform']}"
        assert osr.get("monetization_styles"), f"missing monetization_styles for {r['platform']}"
