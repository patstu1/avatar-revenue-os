"""Add real platform accounts for Tool Signal, Aesthetic Theory, and Body Theory.

Run: docker exec aro-api python scripts/add_real_accounts.py

Idempotent — skips brands that already exist (matched by slug).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from packages.db.session import get_sync_engine
from packages.db.models.core import Organization, Brand
from packages.db.models.accounts import CreatorAccount, AccountPortfolio
from packages.db.enums import Platform, AccountType

engine = get_sync_engine()


def run():
    with Session(engine) as db:
        org = db.query(Organization).first()
        if not org:
            print("No organization found. Run seed.py first.")
            return

        brands_added = 0
        accounts_added = 0

        # ─── Brand: Tool Signal ───────────────────────────────────────
        brand_ts = db.query(Brand).filter_by(slug="tool-signal").first()
        if not brand_ts:
            brand_ts = Brand(
                organization_id=org.id,
                name="Tool Signal",
                slug="tool-signal",
                niche="AI tools",
                sub_niche="AI signals & productivity",
                description="AI-powered tool reviews, signals, and insights",
                target_audience="Tech professionals and AI enthusiasts",
                tone_of_voice="Clear, analytical, trustworthy",
                decision_mode="guarded_auto",
            )
            db.add(brand_ts)
            db.flush()
            brands_added += 1
            print(f"  Created brand: Tool Signal ({brand_ts.id})")
        else:
            print(f"  Brand Tool Signal already exists ({brand_ts.id})")

        ts_accounts = [
            {"platform": Platform.TWITTER, "platform_username": "@toolsignal01", "posting_capacity_per_day": 3, "scale_role": "flagship"},
            {"platform": Platform.INSTAGRAM, "platform_username": "@thetoolsignal", "posting_capacity_per_day": 2, "scale_role": "flagship"},
            {"platform": Platform.TIKTOK, "platform_username": "@toolsignalai", "posting_capacity_per_day": 3, "scale_role": "flagship"},
            {"platform": Platform.YOUTUBE, "platform_username": "@toolsignalco-1", "posting_capacity_per_day": 1, "scale_role": "flagship"},
            {"platform": Platform.LINKEDIN, "platform_username": "tool-signal", "posting_capacity_per_day": 1, "scale_role": "experimental"},
            {"platform": Platform.FACEBOOK, "platform_username": "toolsignaldaily", "posting_capacity_per_day": 1, "scale_role": "experimental"},
        ]
        for acct_data in ts_accounts:
            exists = db.query(CreatorAccount).filter_by(
                brand_id=brand_ts.id,
                platform=acct_data["platform"],
                platform_username=acct_data["platform_username"],
            ).first()
            if not exists:
                acct = CreatorAccount(
                    brand_id=brand_ts.id,
                    account_type=AccountType.ORGANIC,
                    niche_focus="AI tools",
                    language="en",
                    geography="US",
                    **acct_data,
                )
                db.add(acct)
                accounts_added += 1
                print(f"    + {acct_data['platform'].value}: {acct_data['platform_username']}")
            else:
                print(f"    = {acct_data['platform'].value}: {acct_data['platform_username']} (exists)")

        # Portfolio
        if not db.query(AccountPortfolio).filter_by(brand_id=brand_ts.id).first():
            db.add(AccountPortfolio(brand_id=brand_ts.id, name="Tool Signal Portfolio", description="All creator accounts for Tool Signal", strategy="Multi-platform AI tools authority", total_accounts=6))

        # ─── Brand: Aesthetic Theory ──────────────────────────────────
        brand_at = db.query(Brand).filter_by(slug="aesthetic-theory").first()
        if not brand_at:
            brand_at = Brand(
                organization_id=org.id,
                name="Aesthetic Theory",
                slug="aesthetic-theory",
                niche="aesthetics",
                sub_niche="modern aesthetics & treatments",
                description="Modern aesthetics, treatment truths, and what actually makes a difference",
                target_audience="25-45 adults interested in aesthetic treatments and skincare",
                tone_of_voice="Honest, knowledgeable, approachable",
                decision_mode="guarded_auto",
            )
            db.add(brand_at)
            db.flush()
            brands_added += 1
            print(f"  Created brand: Aesthetic Theory ({brand_at.id})")
        else:
            print(f"  Brand Aesthetic Theory already exists ({brand_at.id})")

        at_accounts = [
            {"platform": Platform.YOUTUBE, "platform_username": "@theaesthetictheoryco", "posting_capacity_per_day": 1, "scale_role": "flagship"},
            {"platform": Platform.TIKTOK, "platform_username": "@theaesthetictheoryco", "posting_capacity_per_day": 2, "scale_role": "flagship"},
        ]
        for acct_data in at_accounts:
            exists = db.query(CreatorAccount).filter_by(
                brand_id=brand_at.id,
                platform=acct_data["platform"],
                platform_username=acct_data["platform_username"],
            ).first()
            if not exists:
                acct = CreatorAccount(
                    brand_id=brand_at.id,
                    account_type=AccountType.ORGANIC,
                    niche_focus="aesthetics",
                    language="en",
                    geography="US",
                    **acct_data,
                )
                db.add(acct)
                accounts_added += 1
                print(f"    + {acct_data['platform'].value}: {acct_data['platform_username']}")
            else:
                print(f"    = {acct_data['platform'].value}: {acct_data['platform_username']} (exists)")

        # Portfolio
        if not db.query(AccountPortfolio).filter_by(brand_id=brand_at.id).first():
            db.add(AccountPortfolio(brand_id=brand_at.id, name="Aesthetic Theory Portfolio", description="All creator accounts for Aesthetic Theory", strategy="Short-form aesthetics education", total_accounts=2))

        # ─── Brand: Body Theory ───────────────────────────────────────
        brand_bt = db.query(Brand).filter_by(slug="body-theory").first()
        if not brand_bt:
            brand_bt = Brand(
                organization_id=org.id,
                name="Body Theory",
                slug="body-theory",
                niche="health & beauty",
                sub_niche="body treatments & regenerative aesthetics",
                description="Body treatments, regenerative aesthetics, and what actually makes a visible difference",
                target_audience="25-45 adults interested in body treatments and regenerative aesthetics",
                tone_of_voice="Informative, results-focused, transparent",
                decision_mode="guarded_auto",
            )
            db.add(brand_bt)
            db.flush()
            brands_added += 1
            print(f"  Created brand: Body Theory ({brand_bt.id})")
        else:
            print(f"  Brand Body Theory already exists ({brand_bt.id})")

        bt_accounts = [
            {"platform": Platform.TIKTOK, "platform_username": "@bodytheory.co", "posting_capacity_per_day": 2, "scale_role": "flagship"},
            {"platform": Platform.YOUTUBE, "platform_username": "@bodytheorydaily", "posting_capacity_per_day": 1, "scale_role": "flagship"},
            {"platform": Platform.FACEBOOK, "platform_username": "bodytheorydaily", "posting_capacity_per_day": 1, "scale_role": "flagship"},
            # NOTE: Instagram blocked — Instagram restricting the Gmail. Needs manual resolution.
        ]
        for acct_data in bt_accounts:
            exists = db.query(CreatorAccount).filter_by(
                brand_id=brand_bt.id,
                platform=acct_data["platform"],
                platform_username=acct_data["platform_username"],
            ).first()
            if not exists:
                acct = CreatorAccount(
                    brand_id=brand_bt.id,
                    account_type=AccountType.ORGANIC,
                    niche_focus="body treatments",
                    language="en",
                    geography="US",
                    **acct_data,
                )
                db.add(acct)
                accounts_added += 1
                print(f"    + {acct_data['platform'].value}: {acct_data['platform_username']}")
            else:
                print(f"    = {acct_data['platform'].value}: {acct_data['platform_username']} (exists)")

        # Portfolio
        if not db.query(AccountPortfolio).filter_by(brand_id=brand_bt.id).first():
            db.add(AccountPortfolio(brand_id=brand_bt.id, name="Body Theory Portfolio", description="All creator accounts for Body Theory", strategy="Body treatment education and trust-building", total_accounts=3))

        # ─── Brand: Age Fix Daily ─────────────────────────────────────
        brand_afd = db.query(Brand).filter_by(slug="age-fix-daily").first()
        if not brand_afd:
            brand_afd = Brand(
                organization_id=org.id,
                name="Age Fix Daily",
                slug="age-fix-daily",
                niche="anti-aging",
                sub_niche="age reversal & longevity treatments",
                description="Daily anti-aging insights, treatments, and science-backed age reversal strategies",
                target_audience="30-55 adults interested in anti-aging and longevity",
                tone_of_voice="Science-backed, empowering, direct",
                decision_mode="guarded_auto",
            )
            db.add(brand_afd)
            db.flush()
            brands_added += 1
            print(f"  Created brand: Age Fix Daily ({brand_afd.id})")
        else:
            print(f"  Brand Age Fix Daily already exists ({brand_afd.id})")

        afd_accounts = [
            {"platform": Platform.INSTAGRAM, "platform_username": "@age_fix_daily", "posting_capacity_per_day": 1, "scale_role": "flagship"},
        ]
        for acct_data in afd_accounts:
            exists = db.query(CreatorAccount).filter_by(
                brand_id=brand_afd.id,
                platform=acct_data["platform"],
                platform_username=acct_data["platform_username"],
            ).first()
            if not exists:
                acct = CreatorAccount(
                    brand_id=brand_afd.id,
                    account_type=AccountType.ORGANIC,
                    niche_focus="anti-aging",
                    language="en",
                    geography="US",
                    **acct_data,
                )
                db.add(acct)
                accounts_added += 1
                print(f"    + {acct_data['platform'].value}: {acct_data['platform_username']}")
            else:
                print(f"    = {acct_data['platform'].value}: {acct_data['platform_username']} (exists)")

        # Portfolio
        if not db.query(AccountPortfolio).filter_by(brand_id=brand_afd.id).first():
            db.add(AccountPortfolio(brand_id=brand_afd.id, name="Age Fix Daily Portfolio", description="All creator accounts for Age Fix Daily", strategy="Anti-aging education and trust-building", total_accounts=1))

        # ─── Brand: Velvet Wire ──────────────────────────────────────
        brand_vw = db.query(Brand).filter_by(slug="velvet-wire").first()
        if not brand_vw:
            brand_vw = Brand(
                organization_id=org.id,
                name="Velvet Wire",
                slug="velvet-wire",
                niche="lifestyle & aesthetics",
                sub_niche="curated lifestyle & beauty",
                description="Curated lifestyle, beauty, and aesthetic content",
                target_audience="25-40 style-conscious women interested in aesthetics and lifestyle",
                tone_of_voice="Polished, aspirational, authentic",
                decision_mode="guarded_auto",
            )
            db.add(brand_vw)
            db.flush()
            brands_added += 1
            print(f"  Created brand: Velvet Wire ({brand_vw.id})")
        else:
            print(f"  Brand Velvet Wire already exists ({brand_vw.id})")

        vw_accounts = [
            {"platform": Platform.INSTAGRAM, "platform_username": "@velvetwire.co", "posting_capacity_per_day": 1, "scale_role": "flagship"},
        ]
        for acct_data in vw_accounts:
            exists = db.query(CreatorAccount).filter_by(
                brand_id=brand_vw.id,
                platform=acct_data["platform"],
                platform_username=acct_data["platform_username"],
            ).first()
            if not exists:
                acct = CreatorAccount(
                    brand_id=brand_vw.id,
                    account_type=AccountType.ORGANIC,
                    niche_focus="lifestyle & aesthetics",
                    language="en",
                    geography="US",
                    **acct_data,
                )
                db.add(acct)
                accounts_added += 1
                print(f"    + {acct_data['platform'].value}: {acct_data['platform_username']}")
            else:
                print(f"    = {acct_data['platform'].value}: {acct_data['platform_username']} (exists)")

        # Portfolio
        if not db.query(AccountPortfolio).filter_by(brand_id=brand_vw.id).first():
            db.add(AccountPortfolio(brand_id=brand_vw.id, name="Velvet Wire Portfolio", description="All creator accounts for Velvet Wire", strategy="Curated lifestyle and aesthetics content", total_accounts=1))

        db.commit()
        print(f"\nDone: {brands_added} brands, {accounts_added} accounts added.")
        print("\nWARNING: Body Theory Instagram account is blocked — Instagram restricting the Gmail.")


if __name__ == "__main__":
    run()
