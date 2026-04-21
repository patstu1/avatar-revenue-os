"""AI Avatar Revenue OS — FastAPI Application."""
import logging
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.config import get_settings
from apps.api.middleware import RequestIDMiddleware, SecurityHeadersMiddleware, RedirectHostFixMiddleware, register_exception_handlers
from apps.api.routers import (
    auth, brands, health, organizations, avatars, offers,
    accounts, content, decisions, jobs, providers, dashboard,
    settings as settings_router, discovery, pipeline, analytics,
    brand_scale, brand_growth, brand_phase7, brand_revenue_intel,
    scale_alerts, scale_alerts_root, growth_commander, growth_pack,
    revenue_ceiling_phase_a,
    revenue_ceiling_phase_b,
    revenue_ceiling_phase_c,
    expansion_pack2_phase_a,
    expansion_pack2_phase_b,
    expansion_pack2_phase_c,
)
from apps.api.routers import (
    mxp_experiment_decisions, mxp_contribution, mxp_capacity,
    mxp_offer_lifecycle, mxp_creative_memory, mxp_recovery,
    mxp_deal_desk, mxp_audience_state, mxp_reputation,
    mxp_market_timing, mxp_kill_ledger,
    autonomous_execution,
    autonomous_phase_a,
    autonomous_phase_b,
    autonomous_phase_c,
    autonomous_phase_d,
    brain_phase_a,
    brain_phase_b,
    brain_phase_c,
    brain_phase_d,
    buffer_distribution,
    live_execution,
    live_execution_phase2,
    creator_revenue,
    webhooks,
    operator_console,
    proposals as proposals_router,
    clients as clients_router,
    fulfillment as fulfillment_router,
    qa_delivery as qa_delivery_router,
    provider_registry,
    copilot,
    gatekeeper,
    expansion_advisor,
    content_form,
    content_routing,
    pattern_memory,
    promote_winner,
    capital_allocator,
    account_state_intel,
    quality_governor,
    objection_mining,
    opportunity_cost,
    failure_family,
    command_center,
    landing_pages,
    campaigns,
    affiliate_intel,
    brand_governance,
    enterprise_security,
    workflow_builder,
    hyperscale,
    integrations_listening,
    executive_intel,
    affiliate_enterprise,
    offer_lab,
    revenue_leak_detector,
    digital_twin,
    recovery_engine,
    operator_permission_matrix,
    causal_attribution,
    trend_viral,
    cinema_studio,
    ws_live,
    revenue_intelligence,
    revenue_avenues,
    monetization,
    onboarding,
    revenue_machine,
    control_layer,
    intelligence_hub,
    monetization_hub,
    orchestration_hub,
    governance_hub,
    revenue_maximizer,
    growth_hub,
    gm_ai,
    gm_chat,
    portfolio_command,
    integrations_dashboard,
    oauth,
    ops,
    brain_ops,
    ai_command,
    leads,
    proposal_drain,
    proof_gallery,
    email_pipeline as email_pipeline_router,
    microsoft_inbox_oauth,
)

settings = get_settings()

log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer() if settings.api_env == "development" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(log_level),
)

logger = structlog.get_logger()

_is_dev = settings.api_env == "development"


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup: seed provider registry from env vars for all organizations."""
    try:
        from packages.db.session import get_async_session_factory
        from apps.api.services import provider_registry_service as prs
        from sqlalchemy import select, text

        async with get_async_session_factory()() as db:
            # Get all organizations
            result = await db.execute(text("SELECT id FROM organizations LIMIT 100"))
            org_ids = [row[0] for row in result.fetchall()]

            if org_ids:
                # Get first brand per org to run audit (provider registry is global but needs a brand_id)
                result = await db.execute(text("SELECT id FROM brands LIMIT 1"))
                row = result.fetchone()
                if row:
                    brand_id = row[0]
                    await prs.audit_providers(db, brand_id)
                    await db.commit()
                    logger.info("provider_registry_seeded", brand_id=str(brand_id))
            else:
                logger.info("no_organizations_found_skipping_provider_seed")
    except Exception as e:
        logger.warning("provider_registry_seed_failed", error=str(e))

    yield


app = FastAPI(
    title="AI Avatar Revenue OS",
    description="Production-grade autonomous content monetization platform",
    version="0.1.0",
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    redirect_slashes=True,
    lifespan=lifespan,
)

# --- Middleware (order matters: first added = outermost) ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
    expose_headers=["X-Request-ID"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RedirectHostFixMiddleware)
app.add_middleware(RequestIDMiddleware)

# --- Global exception handlers ---

register_exception_handlers(app)

# --- Sentry (conditional) ---

if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
    )

# --- Routers ---

app.include_router(health.router, tags=["Health"])
app.include_router(ops.router, tags=["Operations"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["Organizations"])
app.include_router(brands.router, prefix="/api/v1/brands", tags=["Brands"])
app.include_router(brand_scale.router, prefix="/api/v1/brands", tags=["Scale & Portfolio"])
app.include_router(brand_growth.router, prefix="/api/v1/brands", tags=["Growth Intelligence"])
app.include_router(brand_phase7.router, prefix="/api/v1/brands", tags=["Phase 7: Sponsor, Roadmap, Cockpit"])
app.include_router(brand_revenue_intel.router, prefix="/api/v1/brands", tags=["Revenue Intelligence"])
app.include_router(scale_alerts.router, prefix="/api/v1/brands", tags=["Scale Alerts & Launch"])
app.include_router(scale_alerts_root.router, prefix="/api/v1", tags=["Scale Alerts & Launch"])
app.include_router(growth_commander.router, prefix="/api/v1/brands", tags=["Growth Commander"])
app.include_router(growth_pack.router, prefix="/api/v1/brands", tags=["Growth Pack"])
app.include_router(growth_pack.router_root, prefix="/api/v1", tags=["Growth Pack"])
app.include_router(revenue_ceiling_phase_a.router, prefix="/api/v1/brands", tags=["Revenue Ceiling Phase A"])
app.include_router(revenue_ceiling_phase_b.router, prefix="/api/v1/brands", tags=["Revenue Ceiling Phase B"])
app.include_router(revenue_ceiling_phase_c.router, prefix="/api/v1/brands", tags=["Revenue Ceiling Phase C"])
app.include_router(expansion_pack2_phase_a.router, prefix="/api/v1/brands", tags=["Expansion Pack 2 Phase A"])
app.include_router(expansion_pack2_phase_b.router, prefix="/api/v1/brands", tags=["Expansion Pack 2 Phase B"])
app.include_router(expansion_pack2_phase_c.router, prefix="/api/v1/brands", tags=["Expansion Pack 2 Phase C"])
app.include_router(avatars.router, prefix="/api/v1/avatars", tags=["Avatars"])
app.include_router(offers.router, prefix="/api/v1/offers", tags=["Offers"])
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["Creator Accounts"])
app.include_router(oauth.router, prefix="/api/v1/oauth", tags=["OAuth Connections"])
app.include_router(content.router, prefix="/api/v1/content", tags=["Content Pipeline"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["Decisions"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["System Jobs"])
app.include_router(providers.router, prefix="/api/v1/providers", tags=["Provider Profiles"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(discovery.router, prefix="/api/v1/brands", tags=["Discovery & Scoring"])
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["Content Pipeline"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics & Attribution"])
app.include_router(mxp_experiment_decisions.router, prefix="/api/v1/brands", tags=["Experiment Decisions"])
app.include_router(mxp_contribution.router, prefix="/api/v1/brands", tags=["Contribution & Attribution"])
app.include_router(mxp_capacity.router, prefix="/api/v1/brands", tags=["Capacity Orchestrator"])
app.include_router(mxp_offer_lifecycle.router, prefix="/api/v1/brands", tags=["Offer Lifecycle"])
app.include_router(mxp_creative_memory.router, prefix="/api/v1/brands", tags=["Creative Memory"])
app.include_router(mxp_recovery.router, prefix="/api/v1/brands", tags=["Recovery Engine"])
app.include_router(mxp_deal_desk.router, prefix="/api/v1/brands", tags=["Deal Desk"])
app.include_router(mxp_audience_state.router, prefix="/api/v1/brands", tags=["Audience State"])
app.include_router(mxp_reputation.router, prefix="/api/v1/brands", tags=["Reputation Monitor"])
app.include_router(mxp_market_timing.router, prefix="/api/v1/brands", tags=["Market Timing"])
app.include_router(mxp_kill_ledger.router, prefix="/api/v1/brands", tags=["Kill Ledger"])
app.include_router(autonomous_execution.router, prefix="/api/v1/brands", tags=["Autonomous Execution"])
app.include_router(autonomous_phase_a.router, prefix="/api/v1/brands", tags=["Autonomous Phase A: Signal Scan, Queue, Warmup"])
app.include_router(autonomous_phase_b.router, prefix="/api/v1/brands", tags=["Autonomous Phase B: Policies, Runner, Distribution, Monetization, Suppression"])
app.include_router(autonomous_phase_c.router, prefix="/api/v1/brands", tags=["Autonomous Phase C: Funnel, Paid, Sponsor, Retention, Recovery"])
app.include_router(autonomous_phase_d.router, prefix="/api/v1/brands", tags=["Autonomous Phase D: Agents, Pressure, Overrides, Blockers, Escalations"])
app.include_router(brain_phase_a.router, prefix="/api/v1/brands", tags=["Brain Phase A: Memory, Account/Opportunity/Execution/Audience States"])
app.include_router(brain_phase_b.router, prefix="/api/v1/brands", tags=["Brain Phase B: Decisions, Policies, Confidence, Cost/Upside, Arbitration"])
app.include_router(brain_phase_c.router, prefix="/api/v1/brands", tags=["Brain Phase C: Agent Mesh, Workflows, Context Bus, Memory Binding"])
app.include_router(brain_phase_d.router, prefix="/api/v1/brands", tags=["Brain Phase D: Meta-Monitoring, Self-Correction, Readiness, Escalation"])
app.include_router(buffer_distribution.router, prefix="/api/v1/brands", tags=["Buffer Distribution: Profiles, Publish, Sync, Blockers"])
app.include_router(buffer_distribution.router_root, prefix="/api/v1", tags=["Buffer Distribution: Profile Update, Job Submit"])
app.include_router(live_execution.router, prefix="/api/v1/brands", tags=["Live Execution: Analytics, Conversions, Experiments, CRM, Email, SMS"])
app.include_router(live_execution_phase2.router, prefix="/api/v1/brands", tags=["Live Execution Phase 2: Webhooks, Triggers, Connectors, Buffer Expansion"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks: Stripe, Shopify, Media Providers"])
app.include_router(leads.router, prefix="/api/v1", tags=["Lead Capture: Public offer page submissions"])
app.include_router(creator_revenue.router, prefix="/api/v1/brands", tags=["Creator Revenue: Opportunities, UGC, Consulting, Premium Access"])
app.include_router(provider_registry.router, prefix="/api/v1/brands", tags=["Provider Registry: Inventory, Readiness, Dependencies, Blockers"])
app.include_router(copilot.router, prefix="/api/v1/brands", tags=["Operator Copilot"])
app.include_router(copilot.router_root, prefix="/api/v1", tags=["Operator Copilot"])
app.include_router(gatekeeper.router, prefix="/api/v1/brands", tags=["AI Gatekeeper: Completion, Truth, Closure, Tests, Dependencies, Contradictions"])
app.include_router(expansion_advisor.router, prefix="/api/v1/brands", tags=["Account Expansion Advisor"])
app.include_router(content_form.router, prefix="/api/v1/brands", tags=["Content Form Selection"])
app.include_router(content_routing.router, prefix="/api/v1/brands", tags=["Content Routing: Tiered Provider Routing"])
app.include_router(pattern_memory.router, prefix="/api/v1/brands", tags=["Pattern Memory: Winning Patterns"])
app.include_router(promote_winner.router, prefix="/api/v1/brands", tags=["Promote-Winner: Experiments, Winners, Losers, Promotion Rules"])
app.include_router(capital_allocator.router, prefix="/api/v1/brands", tags=["Capital Allocator: Budget, Provider Tier, Starvation"])
app.include_router(account_state_intel.router, prefix="/api/v1/brands", tags=["Account-State Intelligence"])
app.include_router(quality_governor.router, prefix="/api/v1/brands", tags=["Quality Governor"])
app.include_router(objection_mining.router, prefix="/api/v1/brands", tags=["Objection Mining"])
app.include_router(opportunity_cost.router, prefix="/api/v1/brands", tags=["Opportunity-Cost Ranking"])
app.include_router(failure_family.router, prefix="/api/v1/brands", tags=["Failure-Family Suppression"])
app.include_router(command_center.router, prefix="/api/v1/brands", tags=["System Command Center"])
app.include_router(landing_pages.router, prefix="/api/v1/brands", tags=["Landing Page Engine"])
app.include_router(campaigns.router, prefix="/api/v1/brands", tags=["Campaign Constructor"])
app.include_router(affiliate_intel.router, prefix="/api/v1/brands", tags=["Affiliate Intelligence"])
app.include_router(brand_governance.router, prefix="/api/v1/brands", tags=["Brand Governance OS"])
app.include_router(enterprise_security.router, prefix="/api/v1", tags=["Enterprise Security + Compliance"])
app.include_router(workflow_builder.router, prefix="/api/v1", tags=["Enterprise Workflow Builder"])
app.include_router(hyperscale.router, prefix="/api/v1", tags=["Hyper-Scale Execution"])
app.include_router(integrations_listening.router, prefix="/api/v1", tags=["Integrations + Listening"])
app.include_router(executive_intel.router, prefix="/api/v1", tags=["Executive Intelligence"])
app.include_router(affiliate_enterprise.router, prefix="/api/v1", tags=["Enterprise Affiliate Governance + Owned Program"])
app.include_router(offer_lab.router, prefix="/api/v1/brands", tags=["Offer Lab"])
app.include_router(revenue_leak_detector.router, prefix="/api/v1/brands", tags=["Revenue Leak Detector"])
app.include_router(digital_twin.router, prefix="/api/v1/brands", tags=["Digital Twin / Simulation"])
app.include_router(recovery_engine.router, prefix="/api/v1", tags=["Recovery / Rollback Engine"])
app.include_router(operator_permission_matrix.router, prefix="/api/v1", tags=["Operator Permission Matrix"])
app.include_router(causal_attribution.router, prefix="/api/v1/brands", tags=["Causal Attribution"])
app.include_router(trend_viral.router, prefix="/api/v1/brands", tags=["Trend / Viral Opportunity Engine"])
app.include_router(cinema_studio.router, prefix="/api/v1/brands", tags=["Cinema Studio"])
app.include_router(ws_live.router, prefix="/api/v1", tags=["WebSocket: Live Revenue Streaming"])
app.include_router(revenue_intelligence.router, prefix="/api/v1/brands", tags=["Revenue Intelligence: Elite"])
app.include_router(revenue_avenues.router, prefix="/api/v1/brands", tags=["Revenue Avenues: SaaS, Pipeline, Launches"])
app.include_router(monetization.router, prefix="/api/v1/monetization", tags=["Monetization Machine: Credits, Plans, Packs, Telemetry"])
app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
app.include_router(revenue_machine.router, prefix="/api/v1/monetization", tags=["Revenue Machine: Operating Model, Readiness, Triggers"])
app.include_router(control_layer.router, prefix="/api/v1", tags=["Control Layer: Operator Command Surface"])
app.include_router(intelligence_hub.router, prefix="/api/v1", tags=["Intelligence Hub: Unified Intelligence Surface"])
app.include_router(monetization_hub.router, prefix="/api/v1", tags=["Monetization Hub: Revenue Operations"])
app.include_router(orchestration_hub.router, prefix="/api/v1", tags=["Orchestration Hub: Jobs, Workers, Providers"])
app.include_router(governance_hub.router, prefix="/api/v1", tags=["Governance Hub: Approvals, Permissions, Memory"])
app.include_router(revenue_maximizer.router, prefix="/api/v1", tags=["Revenue Maximizer: Maximum Revenue Engine"])
app.include_router(growth_hub.router, prefix="/api/v1", tags=["Growth Hub: Audience, Sponsors, Services, Quality, Adaptation"])
app.include_router(gm_ai.router, prefix="/api/v1", tags=["GM AI: Strategic Operating Brain"])
app.include_router(gm_chat.router, prefix="/api/v1", tags=["GM Chat: Conversational Strategic GM"])
app.include_router(portfolio_command.router, prefix="/api/v1", tags=["Portfolio Command Center"])
app.include_router(integrations_dashboard.router, prefix="/api/v1", tags=["Integrations Dashboard"])
app.include_router(brain_ops.router, prefix="/api/v1", tags=["Brain Operations: Runtime State"])
app.include_router(ai_command.router, prefix="/api/v1/brands", tags=["AI Command Center: Provider Stack, Quality, Experiments, Budget, Health, Activity"])
app.include_router(proposal_drain.router, prefix="/api/v1", tags=["Proposal Drain: send_proposal action consumer"])
app.include_router(proof_gallery.router, prefix="/api/v1", tags=["Proof Gallery: Buyer-facing proof assets"])
app.include_router(email_pipeline_router.router, prefix="/api/v1/email", tags=["Email Pipeline: Inboxes, threads, messages, replies"])
app.include_router(microsoft_inbox_oauth.router, prefix="/api/v1", tags=["Microsoft Inbox OAuth: Outlook/Graph inbox connection"])
app.include_router(operator_console.router, prefix="/api/v1", tags=["Operator Console: Pending draft review"])
app.include_router(proposals_router.router, prefix="/api/v1", tags=["Proposals: Conversion backbone"])
app.include_router(clients_router.clients_router, prefix="/api/v1", tags=["Clients: Paid-customer records"])
app.include_router(clients_router.intake_router, prefix="/api/v1", tags=["Intake: Public form + operator list"])
app.include_router(fulfillment_router.router, prefix="/api/v1", tags=["Fulfillment: Projects, briefs, production jobs"])
app.include_router(qa_delivery_router.router, prefix="/api/v1", tags=["QA & Delivery: Production QA loop + deliveries"])

# --- Local media file serving (fallback when S3 is not configured) ---

if not os.getenv("S3_BUCKET"):
    from packages.media.storage import LOCAL_MEDIA_ROOT

    LOCAL_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(LOCAL_MEDIA_ROOT)), name="media")
