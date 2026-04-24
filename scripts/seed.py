"""Seed script: populates the database with realistic local dev data.
Run: docker exec aro-api python scripts/seed.py

Seeds core entities PLUS representative data for all post-core dashboards
so developers see real pages instead of empty shells.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session

from apps.api.services.auth_service import hash_password
from packages.db.enums import (
    AccountType,
    HealthStatus,
    JobStatus,
    MonetizationMethod,
    Platform,
    UserRole,
)
from packages.db.models.accounts import AccountPortfolio, CreatorAccount
from packages.db.models.audience_state import AudienceStateReport
from packages.db.models.autonomous_execution import AutomationExecutionPolicy, AutomationExecutionRun
from packages.db.models.capacity import CapacityReport, QueueAllocationDecision
from packages.db.models.cinema_studio import (
    CharacterBible,
    StudioActivity,
    StudioProject,
    StudioScene,
    StylePreset,
)
from packages.db.models.contribution import ContributionReport
from packages.db.models.core import Avatar, AvatarProviderProfile, Brand, Organization, User, VoiceProviderProfile
from packages.db.models.creative_memory import CreativeMemoryAtom
from packages.db.models.deal_desk import DealDeskRecommendation
from packages.db.models.expansion_pack2_phase_a import (
    CloserAction,
    LeadOpportunity,
    LeadQualificationReport,
    OwnedOfferRecommendation,
)
from packages.db.models.expansion_pack2_phase_b import (
    BundleRecommendation,
    PricingRecommendation,
    ReactivationCampaign,
    RetentionRecommendation,
)
from packages.db.models.expansion_pack2_phase_c import (
    CompetitiveGapReport,
    ProfitGuardrailReport,
    ReferralProgramRecommendation,
    SponsorTarget,
)
from packages.db.models.experiment_decisions import ExperimentDecision
from packages.db.models.kill_ledger import KillLedgerEntry
from packages.db.models.market_timing import MacroSignalEvent, MarketTimingReport
from packages.db.models.offer_lifecycle import OfferLifecycleReport
from packages.db.models.offers import Offer
from packages.db.models.recovery import RecoveryAction, RecoveryIncident
from packages.db.models.reputation import ReputationReport
from packages.db.models.revenue_ceiling_phase_a import FunnelLeakFix, FunnelStageMetric, OfferLadder, OwnedAudienceAsset
from packages.db.models.revenue_ceiling_phase_b import (
    HighTicketOpportunity,
    ProductOpportunity,
    RevenueDensityReport,
    UpsellRecommendation,
)
from packages.db.models.revenue_ceiling_phase_c import (
    MonetizationMixReport,
    PaidPromotionCandidate,
    RecurringRevenueModel,
    SponsorInventory,
    TrustConversionReport,
)
from packages.db.models.scale_alerts import (
    LaunchCandidate,
    LaunchReadinessReport,
    NotificationDelivery,
    OperatorAlert,
    ScaleBlockerReport,
)
from packages.db.models.system import AuditLog, ProviderUsageCost, SystemJob
from packages.db.session import get_sync_engine

engine = get_sync_engine()
now = datetime.now(timezone.utc)


def seed():
    with Session(engine) as db:
        existing = db.query(Organization).first()
        if existing:
            print("Database already seeded. Skipping.")
            return

        # ─── Core: Organization, Users, Brands ─────────────────────────
        org = Organization(name="RevenueLab", slug="revenuelab", plan="pro", settings={"timezone": "America/New_York"})
        db.add(org)
        db.flush()

        admin = User(organization_id=org.id, email="admin@revenuelab.ai", hashed_password=hash_password("admin123"), full_name="Alex Rivera", role=UserRole.ADMIN)
        operator = User(organization_id=org.id, email="operator@revenuelab.ai", hashed_password=hash_password("operator123"), full_name="Jordan Lee", role=UserRole.OPERATOR)
        viewer = User(organization_id=org.id, email="viewer@revenuelab.ai", hashed_password=hash_password("viewer123"), full_name="Morgan Chen", role=UserRole.VIEWER)
        db.add_all([admin, operator, viewer])
        db.flush()

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

        # ─── Avatars ───────────────────────────────────────────────────
        avatar1 = Avatar(brand_id=brand1.id, name="Alex Finance", persona_description="Sharp, friendly finance educator", voice_style="warm, authoritative", visual_style="professional casual")
        avatar2 = Avatar(brand_id=brand2.id, name="Techie", persona_description="Enthusiastic tech reviewer", voice_style="energetic, clear", visual_style="casual, colorful tech setup")
        db.add_all([avatar1, avatar2])
        db.flush()

        db.add_all([
            AvatarProviderProfile(avatar_id=avatar1.id, provider="tavus", is_primary=True, capabilities={"async_video": True}, cost_per_minute=0.50, health_status=HealthStatus.HEALTHY),
            AvatarProviderProfile(avatar_id=avatar1.id, provider="heygen", is_fallback=True, capabilities={"live_streaming": True}, cost_per_minute=0.80, health_status=HealthStatus.HEALTHY),
            VoiceProviderProfile(avatar_id=avatar1.id, provider="elevenlabs", is_primary=True, capabilities={"voice_cloning": True}, cost_per_minute=0.30, health_status=HealthStatus.HEALTHY),
        ])

        # ─── Offers ───────────────────────────────────────────────────
        o1 = Offer(brand_id=brand1.id, name="WealthStack Premium", monetization_method=MonetizationMethod.AFFILIATE, offer_url="https://wealthstack.app/ref", payout_amount=45.0, payout_type="cpa", epc=2.35, conversion_rate=0.038, average_order_value=149.0, priority=1, audience_fit_tags=["budgeting", "investing"])
        o2 = Offer(brand_id=brand1.id, name="BudgetMaster Pro", monetization_method=MonetizationMethod.AFFILIATE, offer_url="https://budgetmaster.co/ref", payout_amount=22.0, payout_type="cpa", epc=1.10, conversion_rate=0.052, average_order_value=79.0, priority=2)
        o3 = Offer(brand_id=brand1.id, name="Finance AI Course", monetization_method=MonetizationMethod.PRODUCT, offer_url="https://financeaipro.com/course", payout_amount=197.0, payout_type="direct", epc=4.20, conversion_rate=0.021, average_order_value=197.0, priority=3)
        o4 = Offer(brand_id=brand2.id, name="AI Tool Suite", monetization_method=MonetizationMethod.AFFILIATE, offer_url="https://aitoolsuite.com/ref", payout_amount=35.0, payout_type="cpa", epc=1.80, conversion_rate=0.042, priority=1)
        db.add_all([o1, o2, o3, o4])
        db.flush()

        # ─── Creator Accounts ─────────────────────────────────────────
        acct1 = CreatorAccount(brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.YOUTUBE, account_type=AccountType.ORGANIC, platform_username="@FinanceAIPro", niche_focus="personal finance", language="en", geography="US", posting_capacity_per_day=2, follower_count=12400, total_revenue=3420.50, total_profit=2890.30, profit_per_post=24.10, revenue_per_mille=8.50, ctr=0.034, conversion_rate=0.028, scale_role="flagship")
        acct2 = CreatorAccount(brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.TIKTOK, account_type=AccountType.ORGANIC, platform_username="@financeai.pro", niche_focus="personal finance", language="en", geography="US", posting_capacity_per_day=3, follower_count=45200, total_revenue=1280.0, total_profit=980.0, profit_per_post=8.90, revenue_per_mille=4.20, ctr=0.021, conversion_rate=0.018, scale_role="experimental")
        acct3 = CreatorAccount(brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.INSTAGRAM, account_type=AccountType.ORGANIC, platform_username="@financeai_pro", niche_focus="personal finance", language="en", geography="US", posting_capacity_per_day=1, follower_count=8900)
        acct4 = CreatorAccount(brand_id=brand2.id, avatar_id=avatar2.id, platform=Platform.YOUTUBE, account_type=AccountType.ORGANIC, platform_username="@TechExplainedAI", niche_focus="technology", language="en", geography="US", posting_capacity_per_day=1, follower_count=5600, total_revenue=890.0, total_profit=720.0)
        acct5 = CreatorAccount(brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.REDDIT, account_type=AccountType.ORGANIC, platform_username="u/FinanceAIPro", niche_focus="personal finance", language="en", geography="US", posting_capacity_per_day=2, follower_count=3200, total_revenue=280.0, total_profit=240.0, profit_per_post=4.80, revenue_per_mille=2.10, ctr=0.015, conversion_rate=0.012, scale_role="experimental")
        acct6 = CreatorAccount(brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.LINKEDIN, account_type=AccountType.ORGANIC, platform_username="financeai-pro", niche_focus="personal finance", language="en", geography="US", posting_capacity_per_day=1, follower_count=4100, total_revenue=560.0, total_profit=490.0, profit_per_post=12.20, revenue_per_mille=5.80, ctr=0.028, conversion_rate=0.022, scale_role="experimental")
        acct7 = CreatorAccount(brand_id=brand1.id, avatar_id=avatar1.id, platform=Platform.FACEBOOK, account_type=AccountType.ORGANIC, platform_username="FinanceAIProPage", niche_focus="personal finance", language="en", geography="US", posting_capacity_per_day=1, follower_count=6800, total_revenue=420.0, total_profit=350.0, profit_per_post=7.00, revenue_per_mille=3.50, ctr=0.019, conversion_rate=0.015, scale_role="experimental")
        acct8 = CreatorAccount(brand_id=brand2.id, avatar_id=avatar2.id, platform=Platform.TWITTER, account_type=AccountType.ORGANIC, platform_username="@TechExplainedX", niche_focus="technology", language="en", geography="US", posting_capacity_per_day=3, follower_count=2400, total_revenue=180.0, total_profit=150.0)
        db.add_all([acct1, acct2, acct3, acct4, acct5, acct6, acct7, acct8])

        portfolio = AccountPortfolio(brand_id=brand1.id, name="Finance AI Growth Portfolio", description="All creator accounts for Finance AI Pro", strategy="Maximize affiliate revenue", total_accounts=3)
        db.add(portfolio)
        db.flush()

        # ─── Provider Costs & System Jobs ─────────────────────────────
        db.add_all([
            ProviderUsageCost(brand_id=brand1.id, provider="elevenlabs", provider_type="voice", operation="text_to_speech", input_units=15000, output_units=1, cost=0.45),
            ProviderUsageCost(brand_id=brand1.id, provider="tavus", provider_type="avatar", operation="video_generation", input_units=1, output_units=1, cost=1.25),
            SystemJob(brand_id=brand1.id, job_name="seed_data_load", job_type="system", queue="default", status=JobStatus.COMPLETED),
        ])

        # ═══════════════════════════════════════════════════════════════
        # POST-CORE DASHBOARD DATA
        # ═══════════════════════════════════════════════════════════════

        b1 = brand1.id
        b2 = brand2.id

        # ─── Scale Alerts ─────────────────────────────────────────────
        alert1 = OperatorAlert(brand_id=b1, alert_type="cannibalization_warning", title="Cannibalization detected on TikTok", summary="Two accounts targeting same sub-niche with overlapping content topics", explanation="Accounts @financeai.pro and @financeai_pro have 68% topic overlap in last 30 days", recommended_action="Differentiate sub-niches or merge accounts", confidence=0.78, urgency=72, expected_upside=340.0, expected_cost=50.0, expected_time_to_signal_days=7, supporting_metrics={"overlap_pct": 0.68, "severity": "medium", "dashboard_section": "content_health"}, status="unread")
        alert2 = OperatorAlert(brand_id=b1, alert_type="fatigue_warning", title="Audience fatigue on YouTube", summary="Engagement rate dropped 22% in 14 days", explanation="CTR fell from 3.4% to 2.6% with consistent posting volume", recommended_action="Rotate content angles or reduce posting frequency", confidence=0.85, urgency=65, expected_upside=200.0, expected_cost=25.0, expected_time_to_signal_days=14, supporting_metrics={"ctr_drop": 0.22, "severity": "high", "dashboard_section": "engagement"}, status="unread")
        db.add_all([alert1, alert2])
        db.flush()

        db.add_all([
            LaunchCandidate(brand_id=b1, candidate_type="flagship_expansion", primary_platform="reddit", niche="personal finance", sub_niche="budgeting", confidence=0.72, urgency=60, expected_monthly_revenue_min=200.0, expected_monthly_revenue_max=800.0, expected_launch_cost=150.0, expected_time_to_signal_days=30, expected_time_to_profit_days=90, supporting_reasons={"niche_demand": 0.8}, required_resources=["content_writer", "reddit_account"]),
            ScaleBlockerReport(brand_id=b1, blocker_type="high_cannibalization", severity="medium", title="Account overlap blocks expansion", explanation="Cannot add 4th account without resolving current topic overlap", recommended_fix="Split sub-niches: budgeting vs investing vs side-hustles", current_value=0.68, threshold_value=0.50),
            LaunchReadinessReport(brand_id=b1, launch_readiness_score=74.5, explanation="Brand is ready for controlled expansion", recommended_action="launch_one", gating_factors={"trust": True, "cannibalization": False, "monetization": True, "capacity": True}, components={"trust_score": 85, "monetization_score": 78, "capacity_score": 70, "cannibalization_risk": 32}),
            NotificationDelivery(brand_id=b1, alert_id=alert1.id, channel="in_app", payload={"title": alert1.title, "summary": alert1.summary}, status="delivered", attempts=1, delivered_at=now.isoformat()),
            NotificationDelivery(brand_id=b1, alert_id=alert2.id, channel="in_app", payload={"title": alert2.title, "summary": alert2.summary}, status="delivered", attempts=1, delivered_at=now.isoformat()),
        ])

        # ─── Revenue Ceiling Phase A ──────────────────────────────────
        db.add_all([
            OfferLadder(brand_id=b1, opportunity_key="wealthstack_x_youtube", tof_content_asset="Top 5 Budget Apps Review", first_order_value=45.0, downstream_value=120.0, lifetime_value=280.0, friction_level="low", upsell_path="course_upsell", retention_path="email_nurture", fallback_path="budget_master", confidence=0.82, explanation="Strong EPC × CVR combo with proven YouTube funnel"),
            OfferLadder(brand_id=b1, opportunity_key="course_x_tiktok", tof_content_asset="3 Money Rules Video", first_order_value=197.0, downstream_value=50.0, lifetime_value=350.0, friction_level="medium", upsell_path="consulting", retention_path="community", fallback_path="affiliate_fallback", confidence=0.65, explanation="Higher friction but strong AOV from direct product"),
            OwnedAudienceAsset(brand_id=b1, asset_type="email_list", content_family="budgeting_tips", channel_value=0.85, direct_vs_capture_score=0.6, cta_variants=["Download free budget template", "Get weekly money tips"]),
            FunnelStageMetric(brand_id=b1, stage="awareness", visitors=45000, conversions=2250, conversion_rate=0.05, period_start=now - timedelta(days=30), period_end=now),
            FunnelStageMetric(brand_id=b1, stage="consideration", visitors=2250, conversions=450, conversion_rate=0.20, period_start=now - timedelta(days=30), period_end=now),
            FunnelStageMetric(brand_id=b1, stage="purchase", visitors=450, conversions=38, conversion_rate=0.084, period_start=now - timedelta(days=30), period_end=now),
            FunnelLeakFix(brand_id=b1, leak_type="weak_cta", stage="consideration", suspected_cause="Generic CTA copy on landing pages", recommended_fix="A/B test benefit-focused CTAs with urgency", estimated_upside=320.0, urgency=70, confidence=0.75),
        ])

        # ─── Revenue Ceiling Phase B ──────────────────────────────────
        from packages.db.models.content import ContentItem
        seed_ci = ContentItem(
            brand_id=b1, title="Budget App Breakdown", content_type="short_video",
            status="published", niche="personal finance",
        )
        db.add(seed_ci)
        db.flush()

        db.add_all([
            HighTicketOpportunity(brand_id=b1, source_offer_id=o3.id, opportunity_key="course_premium_upsell", eligibility_score=0.78, expected_close_rate_proxy=0.65, expected_deal_value=497.0, expected_profit=380.0, confidence=0.72, recommended_offer_path={"path": "course → premium coaching"}, recommended_cta="Book a strategy call"),
            ProductOpportunity(brand_id=b1, opportunity_key="budget_template_pack", product_type="digital_download", product_recommendation="Launch digital template pack for budgeting audience", price_range_min=17.0, price_range_max=47.0, expected_launch_value=2400.0, expected_recurring_value=800.0, build_complexity="low", confidence=0.80),
            RevenueDensityReport(brand_id=b1, content_item_id=seed_ci.id, revenue_per_content_item=42.0, revenue_per_1k_impressions=8.50, profit_per_1k_impressions=6.80, profit_per_audience_member=2.40, monetization_depth_score=0.72, repeat_monetization_score=0.18, ceiling_score=0.68, recommendation="Increase email capture to boost repeat purchases"),
            UpsellRecommendation(brand_id=b1, anchor_offer_id=o3.id, opportunity_key="affiliate_to_course", expected_take_rate=0.12, expected_incremental_value=152.0, best_timing="post_purchase_day_3", best_channel="email", best_next_offer={"name": "Finance AI Course", "price": 197}, best_upsell_sequencing={"step1": "case_study", "step2": "limited_offer"}),
        ])

        # ─── Revenue Ceiling Phase C ──────────────────────────────────
        db.add_all([
            RecurringRevenueModel(brand_id=b1, recurring_potential_score=0.72, audience_fit_score=0.80, churn_risk_proxy=0.15, recommended_offer_type="membership", estimated_monthly_revenue=1200.0, estimated_annual_revenue=12960.0, confidence=0.68),
            SponsorInventory(brand_id=b1, slot_type="video_integration", category="fintech", estimated_cpm=25.0, sponsor_fit_score=0.82, pricing_recommendation={"base": 500, "premium": 1200}),
            TrustConversionReport(brand_id=b1, trust_deficit_score=0.22, missing_trust_elements=["case_studies", "third_party_reviews"], recommended_proof_blocks=[{"type": "testimonial", "priority": 1}, {"type": "case_study", "priority": 2}], estimated_conversion_uplift=0.15, confidence=0.74),
            MonetizationMixReport(brand_id=b1, dependency_risk_score=0.45, current_revenue_mix={"affiliate": 0.65, "product": 0.30, "sponsor": 0.05}, underused_monetization_paths=["membership", "consulting"], next_best_mix={"affiliate": 0.45, "product": 0.30, "membership": 0.15, "sponsor": 0.10}, estimated_margin_uplift=0.12, estimated_ltv_uplift=0.18, confidence=0.70),
            PaidPromotionCandidate(brand_id=b1, slot_type="paid_social", is_eligible=True, gate_result={"impressions": True, "engagement": True, "revenue": True, "roi_or_age": True}, organic_winner_evidence={"avg_engagement": 0.045, "revenue_per_view": 0.008}, estimated_roas=3.2, confidence=0.65),
        ])

        # ─── Expansion Pack 2 Phase A ─────────────────────────────────
        lead1 = LeadOpportunity(brand_id=b1, lead_source="dm", message_text="Hey, I love your budgeting content. Do you offer 1-on-1 coaching?", urgency_score=0.75, budget_proxy_score=0.60, sophistication_score=0.55, offer_fit_score=0.80, trust_readiness_score=0.70, composite_score=0.69, qualification_tier="hot", recommended_action="book_discovery_call", expected_value=142.0, likelihood_to_close=0.58, channel_preference="dm", confidence=0.72, explanation="High urgency DM lead with strong offer fit and trust signals")
        lead2 = LeadOpportunity(brand_id=b1, lead_source="comment", message_text="What budgeting app do you actually use?", urgency_score=0.40, budget_proxy_score=0.35, sophistication_score=0.30, offer_fit_score=0.65, trust_readiness_score=0.50, composite_score=0.43, qualification_tier="warm", recommended_action="send_case_study", expected_value=48.0, likelihood_to_close=0.28, channel_preference="email", confidence=0.55, explanation="Warm comment lead with moderate offer fit")
        db.add_all([lead1, lead2])
        db.flush()

        db.add_all([
            CloserAction(brand_id=b1, lead_opportunity_id=lead1.id, action_type="book_discovery_call", priority=1, channel="dm", subject_or_opener="Hey! Thanks for reaching out about coaching — I'd love to chat about your goals", timing="within_4h", rationale="Hot DM lead with explicit coaching interest", expected_outcome="Booked 15-min discovery call"),
            CloserAction(brand_id=b1, lead_opportunity_id=lead1.id, action_type="send_case_study", priority=2, channel="email", subject_or_opener="How Sarah saved $12K in 6 months with our method", timing="day_2", rationale="Build social proof before pricing conversation"),
            LeadQualificationReport(brand_id=b1, total_leads_scored=2, hot_leads=1, warm_leads=1, cold_leads=0, avg_composite_score=0.56, avg_expected_value=95.0, top_channel="dm", top_recommended_action="book_discovery_call", confidence=0.68, explanation="2 leads scored — 1 hot (DM coaching inquiry), 1 warm (comment engagement)"),
            OwnedOfferRecommendation(brand_id=b1, opportunity_key="repeated_question_budgeting", signal_type="repeated_question", detected_signal="12 comments asking about budget templates in last 30 days", recommended_offer_type="digital_download", offer_name_suggestion="Ultimate Budget Template Pack", price_point_min=17.0, price_point_max=47.0, estimated_demand_score=0.72, estimated_first_month_revenue=680.0, audience_fit="Strong fit — audience actively requesting this product", confidence=0.78, build_priority="high"),
        ])

        # ─── Expansion Pack 2 Phase B ─────────────────────────────────
        db.add_all([
            PricingRecommendation(brand_id=b1, offer_id=o1.id, current_price=45.0, recommended_price=52.0, recommendation_type="price_increase", elasticity_signal=0.35, market_signal=0.60, willingness_to_pay_signal=0.55, confidence=0.68, explanation="Market data shows room for 15% price increase with minimal volume drop", estimated_revenue_impact=840.0),
            BundleRecommendation(brand_id=b1, bundle_name="Finance Starter Pack", offer_ids=[o1.id, o2.id], recommended_bundle_price=55.0, estimated_upsell_rate=0.18, estimated_revenue_impact=1200.0, confidence=0.72, explanation="Value stack strategy — complementary offers with 18% estimated upsell conversion"),
            RetentionRecommendation(brand_id=b1, customer_segment="high_value", churn_risk_score=0.25, strategy_type="personalized_offer", recommended_action="Send exclusive early access to new content", estimated_retention_lift=0.15, confidence=0.70, explanation="High-value segment with low churn risk — personalized retention maintains LTV"),
            ReactivationCampaign(brand_id=b1, campaign_name="Win-Back Q1 2026", campaign_type="discount_offer", target_segment="lapsed_30d", estimated_reactivation_rate=0.12, estimated_revenue_impact=580.0, confidence=0.62, explanation="30-day lapsed users respond well to time-limited discount offers"),
        ])

        # ─── Expansion Pack 2 Phase C ─────────────────────────────────
        db.add_all([
            ReferralProgramRecommendation(brand_id=b1, customer_segment="high_value", recommendation_type="tiered_referral", referral_bonus=25.0, referred_bonus=15.0, estimated_conversion_rate=0.08, estimated_revenue_impact=960.0, confidence=0.70, explanation="High-value customers have 3x referral propensity — tiered bonus maximizes viral coefficient"),
            CompetitiveGapReport(brand_id=b1, competitor_name="BudgetBros", gap_type="pricing_gap", severity="medium", gap_description="Competitor priced 20% lower on similar affiliate offers", estimated_impact=450.0, recommended_action="Differentiate on quality and add exclusive bonuses", confidence=0.65),
            SponsorTarget(brand_id=b1, company_name="FinTechFlow", industry="fintech", estimated_deal_value=2500.0, fit_score=0.82, contact_info={"email": "partnerships@fintechflow.com"}, recommended_package="standard", status="identified"),
            ProfitGuardrailReport(brand_id=b1, metric_name="profit_margin", current_value=0.42, threshold_value=0.30, status="ok", action_recommended="None — healthy margin", estimated_impact=0.0, confidence=0.85),
            ProfitGuardrailReport(brand_id=b1, metric_name="cac_ratio", current_value=0.18, threshold_value=0.25, status="ok", action_recommended="CAC within healthy bounds", estimated_impact=0.0, confidence=0.80),
        ])

        # ═══════════════════════════════════════════════════════════════
        # MAXIMUM STRENGTH PACK (MXP) DATA
        # ═══════════════════════════════════════════════════════════════

        # ─── Experiment Decisions ──────────────────────────────────────
        db.add(ExperimentDecision(
            brand_id=b1, experiment_type="hook_test", target_scope_type="content",
            hypothesis="Short punchy hooks outperform question-based hooks on TikTok",
            expected_upside=0.32, confidence_gap=0.35, priority_score=0.85,
            recommended_allocation=0.15, status="proposed",
            explanation_json={"rationale": "Hook style A/B across 10 next posts (demo row; recompute overwrites with engine-scaled values)"},
        ))

        # ─── Contribution / Attribution ────────────────────────────────
        db.add(ContributionReport(
            brand_id=b1, attribution_model="first_touch", scope_type="content",
            estimated_contribution_value=1420.0, contribution_score=0.74,
            confidence_score=0.68,
            explanation_json={"model": "first_touch", "window": "30d"},
        ))

        # ─── Capacity ─────────────────────────────────────────────────
        db.add(CapacityReport(
            brand_id=b1, capacity_type="content_generation",
            current_capacity=10.0, used_capacity=7.0,
            recommended_volume=8.0, recommended_throttle=0.80,
            expected_profit_impact=240.0, confidence_score=0.75,
            explanation_json={"unit": "pieces/week", "bottleneck": "video_render"},
        ))
        db.add(QueueAllocationDecision(
            brand_id=b1, queue_name="generation", priority_score=90.0,
            allocated_capacity=6.0, deferred_capacity=1.0,
            reason_json={"reason": "flagship accounts prioritised over experimental"},
        ))

        # ─── Offer Lifecycle ──────────────────────────────────────────
        db.add(OfferLifecycleReport(
            brand_id=b1, offer_id=o1.id, lifecycle_state="active",
            health_score=0.82, dependency_risk_score=0.15, decay_score=0.08,
            recommended_next_action="monitor", confidence_score=0.78,
            explanation_json={"state_reason": "Strong CVR and stable EPC"},
        ))

        # ─── Creative Memory ─────────────────────────────────────────
        db.add(CreativeMemoryAtom(
            brand_id=b1, atom_type="hook", platform="youtube",
            niche="personal finance",
            content_json={"text": "Stop doing THIS with your savings", "style": "contrarian"},
            performance_summary_json={"avg_ctr": 0.042, "uses": 5, "avg_retention_30s": 0.68},
            originality_caution_score=0.20, confidence_score=0.72,
        ))

        # ─── Recovery ─────────────────────────────────────────────────
        recovery_inc = RecoveryIncident(
            brand_id=b1, incident_type="conversion_decline", severity="medium",
            scope_type="offer", detected_at=now, status="open",
            explanation_json={"metric": "cvr", "drop_pct": 18, "window": "14d"},
            escalation_state="monitoring",
            recommended_recovery_action="replace_offer",
            automatic_action_taken=None,
        )
        db.add(recovery_inc)
        db.flush()

        db.add(RecoveryAction(
            brand_id=b1, incident_id=recovery_inc.id,
            action_type="replace_offer", action_mode="manual",
            executed=False, confidence_score=0.70,
            expected_effect_json={"expected_cvr_lift": 0.12, "timeline": "7d"},
        ))

        # ─── Deal Desk ────────────────────────────────────────────────
        db.add(DealDeskRecommendation(
            brand_id=b1, scope_type="sponsor", deal_strategy="package_standard",
            pricing_stance="value_anchor",
            packaging_recommendation_json={"includes": ["1 integration", "1 mention", "email blast"]},
            expected_margin=0.55, expected_close_probability=0.62,
            confidence_score=0.70,
            explanation_json={"basis": "Historical CPM and sponsor fit data"},
        ))

        # ─── Audience State ───────────────────────────────────────────
        db.add(AudienceStateReport(
            brand_id=b1, state_name="evaluating", state_score=0.65,
            transition_probabilities_json={"to_committed": 0.30, "to_lapsed": 0.10, "stay": 0.60},
            best_next_action="Send comparison content and social proof",
            confidence_score=0.68,
            explanation_json={"segment": "mid_funnel", "size": 2400},
        ))

        # ─── Reputation ──────────────────────────────────────────────
        db.add(ReputationReport(
            brand_id=b1, scope_type="brand", reputation_risk_score=0.25,
            primary_risks_json=[{"risk_type": "audience_trust_decline", "score": 0.22, "detail": "Moderate"}],
            recommended_mitigation_json=[
                {"risk_type": "audience_trust_decline", "action": "Publish a transparent brand update", "urgency": "low"},
            ],
            expected_impact_if_unresolved=0.18, confidence_score=0.72,
        ))

        # ─── Market Timing ────────────────────────────────────────────
        db.add(MarketTimingReport(
            brand_id=b1, market_category="seasonal_buying", timing_score=0.72,
            active_window="Q1 tax season", recommendation="Push tax-saving content",
            expected_uplift=0.18, confidence_score=0.70,
            explanation_json={
                "explanation": "Seasonal buying window aligns with finance niche peaks.",
                "signal": "Google Trends spike in tax planning queries",
            },
        ))
        db.add(MacroSignalEvent(
            brand_id=b1, signal_type="ad_spend_trend", source_name="seed_baseline",
            signal_metadata_json={"value": 0.65},
            observed_at=now,
        ))

        # ─── Kill Ledger ──────────────────────────────────────────────
        db.add(KillLedgerEntry(
            brand_id=b1, scope_type="content_family", scope_id=brand1.id,
            kill_reason="Sub-1% CTR over 60 days with no improvement trend",
            performance_snapshot_json={"ctr": 0.008, "impressions": 12000, "conversions": 1},
            replacement_recommendation_json={"action": "pivot_to_reels", "expected_ctr": 0.025},
            confidence_score=0.80, killed_at=now,
        ))

        # ─── Autonomous Execution ─────────────────────────────────────
        ae_policy = AutomationExecutionPolicy(
            brand_id=b1, organization_id=org.id,
            operating_mode="guarded_autonomous",
            min_confidence_auto_execute=0.72,
            min_confidence_publish=0.78,
            kill_switch_engaged=False,
            max_auto_cost_usd_per_action=250.0,
            require_approval_above_cost_usd=75.0,
            approval_gates_json={"publish_queue": "approval_required_by_default"},
            extra_policy_json={"loop_steps_registered": ["scan_opportunities", "score_and_rank", "select_account", "generate_content", "qa_gate", "warm_account", "schedule_publish", "monitor_performance", "scale_or_suppress", "self_heal"]},
        )
        db.add(ae_policy)
        db.flush()
        db.add(AutomationExecutionRun(
            brand_id=b1, loop_step="scan_opportunities", status="completed",
            confidence_score=0.85,
            policy_snapshot_json={"operating_mode": "guarded_autonomous", "min_confidence_auto_execute": 0.72},
            input_payload_json={"trigger": "scheduled_scan"},
            output_payload_json={"topics_found": 12, "high_priority": 3},
        ))

        # ═══════════════════════════════════════════════════════════════
        # CINEMA STUDIO DATA
        # ═══════════════════════════════════════════════════════════════

        # ─── Style Presets (global — no brand_id) ────────────────────
        style_cinematic = StylePreset(name="Cinematic", description="Classic Hollywood look with rich contrast, shallow depth of field, and warm tones", category="cinematic", tags=["film", "dramatic", "warm"], is_popular=True)
        style_anime = StylePreset(name="Anime", description="Japanese animation style with vibrant colors, clean lines, and expressive characters", category="anime", tags=["animation", "colorful", "japanese"], is_popular=True)
        style_noir = StylePreset(name="Film Noir", description="High-contrast black and white with dramatic shadows and moody atmosphere", category="noir", tags=["bw", "shadows", "mystery"], is_popular=True)
        style_doc = StylePreset(name="Documentary", description="Natural, realistic look with handheld feel and available lighting", category="documentary", tags=["realistic", "natural", "interview"])
        style_retro = StylePreset(name="Retro VHS", description="Vintage VHS aesthetic with scan lines, color bleeding, and analog warmth", category="retro", tags=["vintage", "80s", "analog"], is_popular=True)
        style_neon = StylePreset(name="Neon Cyberpunk", description="Futuristic neon-lit environments with saturated pinks, blues, and teals", category="fantasy", tags=["neon", "futuristic", "cyberpunk"])
        style_minimal = StylePreset(name="Minimalist", description="Clean, uncluttered compositions with muted colors and generous negative space", category="minimalist", tags=["clean", "simple", "modern"])
        style_abstract = StylePreset(name="Abstract Motion", description="Non-representational flowing shapes, gradients, and particle effects", category="abstract", tags=["particles", "gradients", "motion"])
        db.add_all([style_cinematic, style_anime, style_noir, style_doc, style_retro, style_neon, style_minimal, style_abstract])
        db.flush()

        # ─── Characters ──────────────────────────────────────────────
        char_alex = CharacterBible(
            brand_id=b1, name="Alex Finance", description="A confident 30-something financial educator who breaks down complex investing concepts",
            gender="male", age=32, ethnicity="Caucasian", hair_color="brown", hair_style="short, styled",
            eye_color="blue", build="athletic", personality="Confident, data-driven, slightly humorous",
            role="lead", tags=["finance", "educator", "main_host"],
        )
        char_sarah = CharacterBible(
            brand_id=b1, name="Sarah Budget", description="A relatable millennial who shares her personal journey from debt to financial freedom",
            gender="female", age=28, ethnicity="Asian", hair_color="black", hair_style="long, straight",
            eye_color="brown", build="average", personality="Warm, honest, encouraging",
            role="supporting", tags=["finance", "testimonial", "relatable"],
        )
        char_techie = CharacterBible(
            brand_id=b2, name="Techie", description="An enthusiastic tech reviewer in a colorful home office with gadgets everywhere",
            gender="non-binary", age=25, hair_color="purple", hair_style="short, dyed",
            eye_color="green", build="slim", personality="Energetic, curious, quick-witted",
            role="lead", tags=["tech", "reviewer", "main_host"],
        )
        db.add_all([char_alex, char_sarah, char_techie])
        db.flush()

        # ─── Projects ───────────────────────────────────────────────
        proj1 = StudioProject(
            brand_id=b1, title="Investing 101 Series", description="A 5-part video series teaching beginners the fundamentals of investing",
            genre="documentary", status="active",
        )
        proj2 = StudioProject(
            brand_id=b1, title="Budget Challenge", description="30-day budget challenge video content for TikTok and Reels",
            genre="drama", status="draft",
        )
        proj3 = StudioProject(
            brand_id=b2, title="AI Tools Deep Dive", description="In-depth reviews of the latest AI productivity tools",
            genre="documentary", status="active",
        )
        db.add_all([proj1, proj2, proj3])
        db.flush()

        # ─── Scenes ─────────────────────────────────────────────────
        scene1 = StudioScene(
            project_id=proj1.id, brand_id=b1, title="Hook: Why Most People Lose Money",
            prompt="A confident male presenter in a modern studio, looking directly at camera with a concerned expression. Financial charts showing losses appear behind him. Cinematic lighting with shallow depth of field.",
            negative_prompt="blurry, low quality, cartoon",
            camera_shot="medium_close_up", camera_movement="dolly", lighting="studio",
            mood="tense", style_preset_id=style_cinematic.id, duration_seconds=8.0,
            aspect_ratio="16:9", character_ids=[str(char_alex.id)], order_index=0, status="ready",
        )
        scene2 = StudioScene(
            project_id=proj1.id, brand_id=b1, title="The Rule of 72 Explained",
            prompt="Split screen: left side shows the presenter at a whiteboard drawing the Rule of 72 formula, right side shows compound growth animation. Natural lighting from large windows.",
            camera_shot="wide", camera_movement="static", lighting="natural",
            mood="calm", style_preset_id=style_doc.id, duration_seconds=15.0,
            aspect_ratio="16:9", character_ids=[str(char_alex.id)], order_index=1, status="draft",
        )
        scene3 = StudioScene(
            project_id=proj1.id, brand_id=b1, title="Sarah's Success Story",
            prompt="Young Asian woman sitting in a cozy apartment, talking to camera about her debt-free journey. Warm golden hour lighting streaming through curtains. Subtle background music visualizer.",
            camera_shot="medium", camera_movement="handheld", lighting="golden_hour",
            mood="nostalgic", style_preset_id=style_cinematic.id, duration_seconds=20.0,
            aspect_ratio="16:9", character_ids=[str(char_sarah.id)], order_index=2, status="draft",
        )
        scene4 = StudioScene(
            project_id=proj2.id, brand_id=b1, title="Day 1: The No-Spend Challenge",
            prompt="Fast-paced montage of someone putting away their wallet, making coffee at home, packing lunch. Energetic editing with quick cuts. Neon text overlays showing savings.",
            camera_shot="close_up", camera_movement="whip_pan", lighting="neon",
            mood="energetic", style_preset_id=style_retro.id, duration_seconds=10.0,
            aspect_ratio="9:16", character_ids=[str(char_alex.id)], order_index=0, status="draft",
        )
        scene5 = StudioScene(
            project_id=proj3.id, brand_id=b2, title="AI Coding Assistant Showdown",
            prompt="Tech reviewer at a desk with multiple monitors showing different AI coding tools side by side. Cyberpunk-style neon lighting reflecting off the screens. Quick comparison graphics pop up.",
            camera_shot="over_shoulder", camera_movement="tracking", lighting="neon",
            mood="energetic", style_preset_id=style_neon.id, duration_seconds=12.0,
            aspect_ratio="16:9", character_ids=[str(char_techie.id)], order_index=0, status="ready",
        )
        db.add_all([scene1, scene2, scene3, scene4, scene5])
        db.flush()

        # ─── Studio Activity ────────────────────────────────────────
        db.add_all([
            StudioActivity(brand_id=b1, activity_type="project_created", entity_id=proj1.id, entity_name=proj1.title),
            StudioActivity(brand_id=b1, activity_type="project_created", entity_id=proj2.id, entity_name=proj2.title),
            StudioActivity(brand_id=b2, activity_type="project_created", entity_id=proj3.id, entity_name=proj3.title),
            StudioActivity(brand_id=b1, activity_type="scene_created", entity_id=scene1.id, entity_name=scene1.title),
            StudioActivity(brand_id=b1, activity_type="scene_created", entity_id=scene2.id, entity_name=scene2.title),
            StudioActivity(brand_id=b1, activity_type="scene_created", entity_id=scene3.id, entity_name=scene3.title),
            StudioActivity(brand_id=b1, activity_type="character_created", entity_id=char_alex.id, entity_name=char_alex.name),
            StudioActivity(brand_id=b1, activity_type="character_created", entity_id=char_sarah.id, entity_name=char_sarah.name),
            StudioActivity(brand_id=b2, activity_type="character_created", entity_id=char_techie.id, entity_name=char_techie.name),
        ])

        # ─── Audit Logs ───────────────────────────────────────────────
        db.add_all([
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="human", action="seed.executed", entity_type="system", details={"source": "seed_script", "version": "2.0"}),
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="system", action="organization.created", entity_type="organization", entity_id=org.id),
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="system", action="brand.created", entity_type="brand", entity_id=brand1.id),
            AuditLog(organization_id=org.id, user_id=admin.id, actor_type="system", action="brand.created", entity_type="brand", entity_id=brand2.id),
        ])

        db.commit()
        print("Seed complete (v3 — full dashboard + Cinema Studio data):")
        print(f"  1 organization: {org.name}")
        print("  3 users (admin/operator/viewer)")
        print("  2 brands with avatars and provider profiles")
        print("  4 offers")
        print("  8 creator accounts (YT, TT, IG, Reddit, LinkedIn, FB, X) + 1 portfolio")
        print("  Scale alerts: 2 alerts, 1 launch candidate, 1 blocker, 1 readiness report, 2 notifications")
        print("  Revenue Ceiling A: 2 offer ladders, 1 audience asset, 3 funnel metrics, 1 leak fix")
        print("  Revenue Ceiling B: 1 high-ticket, 1 product opp, 1 density report, 1 upsell")
        print("  Revenue Ceiling C: 1 recurring, 1 sponsor inventory, 1 trust, 1 mix, 1 paid promo")
        print("  EP2A: 2 leads, 2 closer actions, 1 qual report, 1 owned offer rec")
        print("  EP2B: 1 pricing, 1 bundle, 1 retention, 1 reactivation")
        print("  EP2C: 1 referral, 1 competitive gap, 1 sponsor target, 2 profit guardrails")
        print("  MXP Experiment Decisions: 1 experiment")
        print("  MXP Contribution: 1 attribution report")
        print("  MXP Capacity: 1 capacity report, 1 queue allocation")
        print("  MXP Offer Lifecycle: 1 lifecycle report")
        print("  MXP Creative Memory: 1 atom")
        print("  MXP Recovery: 1 incident, 1 action")
        print("  MXP Deal Desk: 1 recommendation")
        print("  MXP Audience State: 1 state report")
        print("  MXP Reputation: 1 risk report")
        print("  MXP Market Timing: 1 timing report")
        print("  MXP Kill Ledger: 1 kill entry")
        print("  Autonomous Execution: 1 policy, 1 run")
        print("  Cinema Studio: 8 style presets, 3 characters, 3 projects, 5 scenes, 9 activity entries")
        print("  Login: admin@revenuelab.ai / admin123")


if __name__ == "__main__":
    seed()
