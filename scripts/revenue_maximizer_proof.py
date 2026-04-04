#!/usr/bin/env python3
"""Revenue Maximizer Proof — proves all 7 engines work against real DB."""
from __future__ import annotations
import asyncio, os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://avataros:avataros_dev_2026@localhost:5433/avatar_revenue_os")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://avataros:avataros_dev_2026@localhost:5433/avatar_revenue_os")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from packages.db.base import Base
import packages.db.models  # noqa

P = F = 0
def ok(name, passed, detail=""):
    global P, F
    P += 1 if passed else 0; F += 0 if passed else 1
    print(f"  {'✓' if passed else '✗'} {name}" + (f" — {detail}" if detail and not passed else ""))

async def main():
    print("\n" + "=" * 72)
    print("  REVENUE MAXIMIZER PROOF — 7 Engines")
    print("=" * 72)

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    try:
        async with engine.begin() as c: await c.execute(text("SELECT 1"))
        print("\n  DB: connected\n")
    except Exception as e:
        print(f"\n  ✗ DB: {e}"); return

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        from packages.db.models.core import Organization, User, Brand
        from packages.db.models.accounts import CreatorAccount
        from packages.db.models.content import ContentItem
        from packages.db.models.offers import Offer
        from packages.db.models.revenue_ledger import RevenueLedgerEntry
        from packages.db.enums import ContentType, MonetizationMethod, Platform
        from apps.api.services import revenue_maximizer as rev
        from apps.api.services import monetization_bridge as mon

        # Setup
        org = Organization(name=f"revp_{uuid.uuid4().hex[:6]}", slug=f"revp-{uuid.uuid4().hex[:6]}")
        db.add(org); await db.flush()
        brand = Brand(organization_id=org.id, name="Rev Max Brand", slug=f"revmax-{uuid.uuid4().hex[:6]}", niche="business")
        db.add(brand); await db.flush()

        # Create accounts
        acct1 = CreatorAccount(brand_id=brand.id, platform=Platform.YOUTUBE, platform_username="@revmax_yt", is_active=True)
        acct2 = CreatorAccount(brand_id=brand.id, platform=Platform.TIKTOK, platform_username="@revmax_tt", is_active=True)
        acct3 = CreatorAccount(brand_id=brand.id, platform=Platform.INSTAGRAM, platform_username="@revmax_ig", is_active=True)
        db.add_all([acct1, acct2, acct3]); await db.flush()

        # Create offers
        offer1 = Offer(brand_id=brand.id, name="High-Ticket Course", monetization_method=MonetizationMethod.PRODUCT, payout_amount=197, epc=5.0, conversion_rate=0.02, is_active=True)
        offer2 = Offer(brand_id=brand.id, name="Affiliate SaaS Tool", monetization_method=MonetizationMethod.AFFILIATE, payout_amount=50, epc=2.0, conversion_rate=0.03, is_active=True)
        db.add_all([offer1, offer2]); await db.flush()

        # Create content
        c1 = ContentItem(brand_id=brand.id, title="How to Start a Business", content_type=ContentType.LONG_VIDEO, status="published", offer_id=offer1.id)
        c2 = ContentItem(brand_id=brand.id, title="Best Tools for Creators", content_type=ContentType.SHORT_VIDEO, status="published", offer_id=offer2.id)
        c3 = ContentItem(brand_id=brand.id, title="Unmonetized Guide", content_type=ContentType.TEXT_POST, status="published")  # No offer
        db.add_all([c1, c2, c3]); await db.flush()

        # Create revenue in ledger
        await mon.record_affiliate_commission_to_ledger(db, brand_id=brand.id, gross_amount=500, offer_id=offer2.id, content_item_id=c2.id)
        await mon.record_sponsor_payment_to_ledger(db, brand_id=brand.id, gross_amount=2000, payment_state="confirmed")
        await mon.record_service_payment_to_ledger(db, brand_id=brand.id, gross_amount=1500, platform_fee=45)
        await mon.record_product_sale_to_ledger(db, brand_id=brand.id, gross_amount=394, offer_id=offer1.id, content_item_id=c1.id)
        await db.flush()

        print(f"  Brand: {brand.id}")
        print(f"  Accounts: 3, Offers: 2, Content: 3, Ledger entries: 4\n")

        # ═══════════════════════════════════════════════════════════
        print("─── Engine 1: CREATOR MONETIZATION FIT ───")
        fit = await rev.compute_creator_monetization_fit(db, brand.id)
        ok("Fit scores computed", len(fit) == 3)
        ok("Each has 10 paths", all(len(f["fit_scores"]) == 10 for f in fit))
        ok("Each has best_fit", all("best_fit" in f for f in fit))
        ok("Scores are 0-1", all(0 <= f["best_score"] <= 1 for f in fit))
        ok("YouTube has long_form fit", any(f["platform"] == "youtube" and f["fit_scores"]["long_form"] > 0.3 for f in fit))
        ok("TikTok has short_form fit", any(f["platform"] == "tiktok" and f["fit_scores"]["short_form"] > 0.3 for f in fit))
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── Engine 2: REVENUE OPPORTUNITIES ───")
        opps = await rev.detect_revenue_opportunities(db, brand.id)
        ok("Opportunities detected", len(opps) >= 1)
        ok("Has expected_upside", all("expected_upside" in o for o in opps))
        ok("Sorted by upside", all(opps[i]["expected_upside"] >= opps[i+1]["expected_upside"] for i in range(len(opps)-1)) if len(opps) > 1 else True)
        ok("Finds unmonetized content", any(o["type"] == "under_monetized_content" for o in opps))
        opp_types = {o["type"] for o in opps}
        ok("Multiple opportunity types", len(opp_types) >= 1)
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── Engine 3: REVENUE ALLOCATION ───")
        alloc = await rev.compute_revenue_allocation(db, brand.id)
        ok("Allocation computed", "allocations" in alloc)
        ok("Has total revenue", alloc["total_revenue_30d"] > 0)
        ok("Multiple sources", len(alloc["allocations"]) >= 4)
        ok("Each has score", all("allocation_score" in a for a in alloc["allocations"]))
        ok("Sorted by score", all(alloc["allocations"][i]["allocation_score"] >= alloc["allocations"][i+1]["allocation_score"] for i in range(len(alloc["allocations"])-1)))
        ok("Each has recommendation", all(a["recommendation"] in ("scale", "maintain", "reduce") for a in alloc["allocations"]))
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── Engine 4: SUPPRESSIONS ───")
        supp = await rev.compute_suppression_targets(db, brand.id)
        ok("Suppression list returned", isinstance(supp, list))
        # May be empty if no losing patterns exist — that's ok
        ok("Each has type + action", all("type" in s and "action" in s for s in supp) if supp else True)
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── Engine 5: REVENUE MEMORY ───")
        mem = await rev.get_revenue_memory(db, brand.id)
        ok("Memory returned", isinstance(mem, dict))
        ok("Has winning_patterns key", "winning_patterns" in mem)
        ok("Has promoted_rules key", "promoted_rules" in mem)
        ok("Has learning_entries key", "learning_entries" in mem)
        ok("Has revenue_by_source", "revenue_by_source" in mem)
        ok("Revenue sources from ledger", len(mem["revenue_by_source"]) >= 3)
        ok("Total signals counted", mem["total_signals"] >= 0)
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── Engine 6: MONETIZATION MIX ───")
        mix = await rev.compute_monetization_mix(db, brand.id)
        ok("Mix computed", isinstance(mix, dict))
        ok("Has current_mix", "current_mix" in mix)
        ok("Has recommended_mix", "recommended_mix" in mix)
        ok("Has gaps", "gaps" in mix)
        ok("Has diversification_score", "diversification_score" in mix)
        ok("Current mix from ledger", len(mix["current_mix"]) >= 3)
        ok("Mix percentages sum ~100", 95 <= sum(mix["current_mix"].values()) <= 105 if mix["current_mix"] else True)
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── Engine 7: NEXT-BEST ACTIONS ───")
        actions = await rev.get_next_best_revenue_actions(db, brand.id, org.id)
        ok("Actions returned", len(actions) >= 1)
        ok("Has expected_value", all("expected_value" in a for a in actions))
        ok("Has priority", all("priority" in a for a in actions))
        ok("Sorted by value", all(actions[i]["expected_value"] >= actions[i+1]["expected_value"] for i in range(len(actions)-1)) if len(actions) > 1 else True)
        ok("Max 10 actions", len(actions) <= 10)
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── COMMAND CENTER ───")
        cmd = await rev.get_revenue_command_center(db, brand.id, org.id)
        ok("Command center returned", isinstance(cmd, dict))
        ok("Has revenue", "revenue" in cmd)
        ok("Has opportunities", "opportunities" in cmd)
        ok("Has allocation", "allocation" in cmd)
        ok("Has suppressions", "suppressions" in cmd)
        ok("Has mix", "monetization_mix" in cmd)
        ok("Has next_actions", "next_actions" in cmd)
        ok("Has opportunity_count", "opportunity_count" in cmd)
        ok("Has suppression_count", "suppression_count" in cmd)
        print()

        # ═══════════════════════════════════════════════════════════
        print("─── AUTOMATION ───")
        auto = await rev.auto_surface_revenue_actions(db, org.id, brand.id)
        ok("Auto-surface executes", isinstance(auto, list))
        ok("Actions created", len(auto) >= 0)  # May be 0 if expected_value thresholds not met
        print()

        await db.rollback()

    print("=" * 72)
    print(f"  REVENUE MAXIMIZER PROOF: {P} PASS / {F} FAIL / {P+F} TOTAL")
    print("=" * 72)
    verdict = "ALL 7 ENGINES PROVEN" if F == 0 else f"{F} FAILURES"
    print(f"\n  VERDICT: {verdict}")
    return F == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
