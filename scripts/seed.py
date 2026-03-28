"""Seed script: populates the database with realistic local dev data.
Run: docker exec aro-api python scripts/seed.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from packages.db.session import get_sync_engine
from packages.db.models.core import Organization, User, Brand, Avatar, AvatarProviderProfile, VoiceProviderProfile
from packages.db.models.offers import Offer
from packages.db.models.accounts import CreatorAccount, AccountPortfolio
from packages.db.models.system import AuditLog, SystemJob, ProviderUsageCost
from packages.db.enums import (
    UserRole, Platform, AccountType, MonetizationMethod,
    HealthStatus, JobStatus,
)
from apps.api.services.auth_service import hash_password

engine = get_sync_engine()


def seed():
    with Session(engine) as db:
        existing = db.query(Organization).first()
        if existing:
            print("Database already seeded. Skipping.")
            return

        # Organization
        org = Organization(name="RevenueLab", slug="revenuelab", plan="pro", settings={"timezone": "America/New_York"})
        db.add(org)
        db.flush()

        # Users
        admin = User(
            organization_id=org.id, email="admin@revenuelab.ai",
            hashed_password=hash_password("admin123"), full_name="Alex Rivera",
            role=UserRole.ADMIN,
        )
        operator = User(
            organization_id=org.id, email="operator@revenuelab.ai",
            hashed_password=hash_password("operator123"), full_name="Jordan Lee",
            role=UserRole.OPERATOR,
        )
        viewer = User(
            organization_id=org.id, email="viewer@revenuelab.ai",
            hashed_password=hash_password("viewer123"), full_name="Morgan Chen",
            role=UserRole.VIEWER,
        )
        db.add_all([admin, operator, viewer])
        db.flush()

        # Brands
        brand1 = Brand(
            organization_id=org.id, name="FinanceAI Pro", slug="finance-ai-pro",
            niche="personal finance", sub_niche="budgeting & investing",
            description="AI-powered personal finance education through engaging short-form video",
            target_audience="18-35 year olds interested in building wealth",
            tone_of_voice="Confident, data-driven, slightly contrarian",
            decision_mode="guarded_auto",
        )
        brand2 = Brand(
            organization_id=org.id, name="TechExplained", slug="tech-explained",
            niche="technology", sub_niche="AI & productivity tools",
            description="Breaking down complex tech for everyday users",
            target_audience="25-45 tech-curious professionals",
            tone_of_voice="Approachable, clear, enthusiastic",
            decision_mode="manual_override",
        )
        db.add_all([brand1, brand2])
        db.flush()

        # Avatars
        avatar1 = Avatar(
            brand_id=brand1.id, name="Alex Finance",
            persona_description="A sharp, friendly finance educator who cuts through noise with data",
            voice_style="warm, authoritative, slightly fast-paced",
            visual_style="professional casual, modern studio background",
            personality_traits={"openness": 0.8, "conscientiousness": 0.9, "humor": 0.6},
            speaking_patterns={"filler_rate": "low", "pacing": "dynamic", "emphasis": "data_points"},
        )
        avatar2 = Avatar(
            brand_id=brand2.id, name="Techie",
            persona_description="An enthusiastic tech reviewer who makes complex concepts simple",
            voice_style="energetic, clear, conversational",
            visual_style="casual, colorful tech setup background",
        )
        db.add_all([avatar1, avatar2])
        db.flush()

        # Avatar Provider Profiles
        tavus_profile = AvatarProviderProfile(
            avatar_id=avatar1.id, provider="tavus", is_primary=True,
            capabilities={"async_video": True, "lip_sync": True, "max_duration_sec": 300},
            cost_per_minute=0.50, health_status=HealthStatus.HEALTHY,
        )
        heygen_profile = AvatarProviderProfile(
            avatar_id=avatar1.id, provider="heygen", is_fallback=True,
            capabilities={"live_streaming": True, "interactive": True},
            cost_per_minute=0.80, health_status=HealthStatus.HEALTHY,
        )
        db.add_all([tavus_profile, heygen_profile])

        # Voice Provider Profiles
        eleven_profile = VoiceProviderProfile(
            avatar_id=avatar1.id, provider="elevenlabs", is_primary=True,
            capabilities={"voice_cloning": True, "streaming": True, "languages": ["en", "es"]},
            cost_per_minute=0.30, health_status=HealthStatus.HEALTHY,
        )
        openai_voice = VoiceProviderProfile(
            avatar_id=avatar1.id, provider="openai_realtime", is_fallback=True,
            capabilities={"realtime_conversation": True, "function_calling": True},
            cost_per_minute=0.12, health_status=HealthStatus.HEALTHY,
        )
        db.add_all([eleven_profile, openai_voice])

        # Offers
        offers = [
            Offer(
                brand_id=brand1.id, name="WealthStack Premium", monetization_method=MonetizationMethod.AFFILIATE,
                offer_url="https://wealthstack.app/ref/financeai", payout_amount=45.0, payout_type="cpa",
                epc=2.35, conversion_rate=0.038, average_order_value=149.0, priority=1,
                audience_fit_tags=["budgeting", "investing", "millennials"],
            ),
            Offer(
                brand_id=brand1.id, name="BudgetMaster Pro", monetization_method=MonetizationMethod.AFFILIATE,
                offer_url="https://budgetmaster.co/partner/financeai", payout_amount=22.0, payout_type="cpa",
                epc=1.10, conversion_rate=0.052, average_order_value=79.0, priority=2,
            ),
            Offer(
                brand_id=brand1.id, name="Finance AI Course", monetization_method=MonetizationMethod.PRODUCT,
                offer_url="https://financeaipro.com/course", payout_amount=197.0, payout_type="direct",
                epc=4.20, conversion_rate=0.021, average_order_value=197.0, priority=3,
            ),
            Offer(
                brand_id=brand2.id, name="AI Tool Suite Affiliate", monetization_method=MonetizationMethod.AFFILIATE,
                offer_url="https://aitoolsuite.com/ref/techexplained", payout_amount=35.0, payout_type="cpa",
                epc=1.80, conversion_rate=0.042, priority=1,
            ),
        ]
        db.add_all(offers)

        # Creator Accounts
        accounts = [
            CreatorAccount(
                brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.YOUTUBE,
                account_type=AccountType.ORGANIC, platform_username="@FinanceAIPro",
                niche_focus="personal finance", sub_niche_focus="budgeting",
                language="en", geography="US", monetization_focus="affiliate",
                posting_capacity_per_day=2, follower_count=12400,
                total_revenue=3420.50, total_profit=2890.30, profit_per_post=24.10,
                revenue_per_mille=8.50, ctr=0.034, conversion_rate=0.028,
            ),
            CreatorAccount(
                brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.TIKTOK,
                account_type=AccountType.ORGANIC, platform_username="@financeai.pro",
                niche_focus="personal finance", sub_niche_focus="money tips",
                language="en", geography="US", monetization_focus="affiliate",
                posting_capacity_per_day=3, follower_count=45200,
                total_revenue=1280.00, total_profit=980.00, profit_per_post=8.90,
                revenue_per_mille=4.20, ctr=0.021, conversion_rate=0.018,
            ),
            CreatorAccount(
                brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.INSTAGRAM,
                account_type=AccountType.ORGANIC, platform_username="@financeai_pro",
                niche_focus="personal finance", language="en", geography="US",
                posting_capacity_per_day=1, follower_count=8900,
            ),
            CreatorAccount(
                brand_id=brand2.id, avatar_id=avatar2.id, platform=Platform.YOUTUBE,
                account_type=AccountType.ORGANIC, platform_username="@TechExplainedAI",
                niche_focus="technology", language="en", geography="US",
                posting_capacity_per_day=1, follower_count=5600,
                total_revenue=890.00, total_profit=720.00,
            ),
        ]
        db.add_all(accounts)

        # Portfolio
        portfolio = AccountPortfolio(
            brand_id=brand1.id, name="Finance AI Growth Portfolio",
            description="All creator accounts for the Finance AI Pro brand",
            strategy="Maximize affiliate revenue through short-form content",
            total_accounts=3,
        )
        db.add(portfolio)

        # Provider Usage Costs
        costs = [
            ProviderUsageCost(
                brand_id=brand1.id, provider="elevenlabs", provider_type="voice",
                operation="text_to_speech", input_units=15000, output_units=1,
                cost=0.45,
            ),
            ProviderUsageCost(
                brand_id=brand1.id, provider="tavus", provider_type="avatar",
                operation="video_generation", input_units=1, output_units=1,
                cost=1.25,
            ),
            ProviderUsageCost(
                brand_id=brand1.id, provider="openai", provider_type="llm",
                operation="script_generation", input_units=2000, output_units=800,
                cost=0.08,
            ),
        ]
        db.add_all(costs)

        # System Jobs
        jobs = [
            SystemJob(
                brand_id=brand1.id, job_name="seed_data_load", job_type="system",
                queue="default", status=JobStatus.COMPLETED,
            ),
        ]
        db.add_all(jobs)

        # Audit Logs
        audit_entries = [
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="human", action="seed.executed", entity_type="system", details={"source": "seed_script"}),
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="system", action="organization.created", entity_type="organization", entity_id=org.id),
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="system", action="brand.created", entity_type="brand", entity_id=brand1.id),
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="system", action="brand.created", entity_type="brand", entity_id=brand2.id),
        ]
        db.add_all(audit_entries)

        db.commit()
        print(f"Seed complete:")
        print(f"  1 organization: {org.name}")
        print(f"  3 users (admin/operator/viewer)")
        print(f"  2 brands")
        print(f"  2 avatars with provider profiles")
        print(f"  {len(offers)} offers")
        print(f"  {len(accounts)} creator accounts")
        print(f"  {len(costs)} provider usage records")
        print(f"  Login: admin@revenuelab.ai / admin123")


if __name__ == "__main__":
    seed()
